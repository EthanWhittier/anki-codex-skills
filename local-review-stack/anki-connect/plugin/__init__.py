# Copyright 2016-2021 Alex Yatskov
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

import aqt

required_anki_version = (23, 10, 0)
VERSION_SUFFIXES = ["b", "rc"]

version_string = aqt.appVersion
for suffix in VERSION_SUFFIXES:
    version_string = version_string.replace(suffix, ".")
anki_version = tuple(int(segment) for segment in version_string.split(".") if segment)

# Append to tuple when versions have different number of segments (ie. 25.07 vs 25.07.0)
anki_version += (0,) * (len(required_anki_version) - len(anki_version))
required_anki_version += (0,) * (len(anki_version) - len(required_anki_version))
if anki_version < required_anki_version:
    raise Exception(f"Minimum Anki version supported: {required_anki_version[0]}.{required_anki_version[1]}.{required_anki_version[2]}")

import base64
import copy
import glob
import hashlib
import inspect
import json
import os
import os.path
import platform
import re
import threading
import time
import unicodedata
import uuid
from collections import OrderedDict
from pathlib import Path

import anki
import anki.exporting
import anki.storage
from anki.cards import Card
from anki.consts import MODEL_CLOZE
from anki.exporting import AnkiPackageExporter
from anki.importing import AnkiPackageImporter
from anki.notes import Note
from anki.errors import NotFoundError
from anki.scheduler.base import ScheduleCardsAsNew
from anki.scheduler.v3 import CardAnswer
from aqt.qt import Qt, QTimer, QMessageBox, QCheckBox

from .web import format_exception_reply, format_success_reply
from .edit import Edit
from . import web, util


def loadChatReviewCompatibility():
    path = Path(__file__).with_name('chat_review_compat.json')
    try:
        with path.open(encoding='utf-8') as handle:
            data = json.load(handle)
    except (OSError, ValueError, TypeError):
        data = {}
    versions = data.get('testedAnkiVersions', [])
    if not isinstance(versions, list) or not all(isinstance(item, str) for item in versions):
        versions = []
    return tuple(versions)


#
# AnkiConnect
#

class AnkiConnect:
    CHAT_REVIEW_PROTOCOL = 'chat-review/v1'
    CHAT_REVIEW_TESTED_ANKI_VERSIONS = loadChatReviewCompatibility()
    CHAT_REVIEW_PENDING_TTL_SECONDS = 24 * 60 * 60
    CHAT_REVIEW_COMPLETED_TTL_SECONDS = 24 * 60 * 60
    CHAT_REVIEW_MAX_PENDING = 32
    CHAT_REVIEW_MAX_COMPLETED = 1000

    def __init__(self):
        self.log = None
        self.timer = None
        self.server = web.WebServer(self.handler)
        # AnkiConnect requests run on Anki's main thread today. Keep an explicit
        # lock as part of the protocol contract so registry mutations remain
        # serialized if the transport implementation changes.
        self.chatReviewLock = threading.RLock()
        self.chatReviewPending = OrderedDict()
        self.chatReviewCompleted = OrderedDict()
        self.chatReviewExpired = OrderedDict()
        self.chatReviewStatusObserved = {}

    def initLogging(self):
        logPath = util.setting('apiLogPath')
        if logPath is not None:
            self.log = open(logPath, 'w')

    def startWebServer(self):
        try:
            self.server.listen()

            # only keep reference to prevent garbage collection
            self.timer = QTimer()
            self.timer.timeout.connect(self.advance)
            self.timer.start(util.setting('apiPollInterval'))
        except:
            QMessageBox.critical(
                self.window(),
                'AnkiConnect',
                'Failed to listen on port {}.\nMake sure it is available and is not in use.'.format(util.setting('webBindPort'))
            )

    def save_model(self, models, ankiModel):
        models.update_dict(ankiModel)

    def logEvent(self, name, data):
        if self.log is not None:
            self.log.write('[{}]\n'.format(name))
            json.dump(self.redactChatReviewLogData(data), self.log, indent=4, sort_keys=True)
            self.log.write('\n\n')
            self.log.flush()


    def redactChatReviewLogData(self, value):
        if isinstance(value, dict):
            redacted = {}
            for key, item in value.items():
                if key in ('ticket', 'reviewTicket', 'sessionId', 'reviewSessionId') and isinstance(item, str):
                    digest = hashlib.sha256(item.encode('utf-8')).hexdigest()[:12]
                    redacted[key] = '<sha256:{}>'.format(digest)
                else:
                    redacted[key] = self.redactChatReviewLogData(item)
            return redacted
        if isinstance(value, list):
            return [self.redactChatReviewLogData(item) for item in value]
        return value


    def chatReviewError(self, code, message):
        raise Exception('{}: {}'.format(code, message))


    def chatReviewVersionVerified(self):
        return aqt.appVersion in self.CHAT_REVIEW_TESTED_ANKI_VERSIONS


    def requireChatReviewVersionVerified(self):
        if not self.chatReviewVersionVerified():
            self.chatReviewError(
                'ANKI_VERSION_UNVERIFIED',
                'Anki {} has not passed the isolated chat-review compatibility gate'.format(
                    aqt.appVersion
                ),
            )


    def chatReviewFsrsStatus(self):
        collection = self.collection()
        deckId = collection.decks.selected()
        enabled = bool(collection.decks.get_deck_configs_for_update(deckId).fsrs)
        return {
            'enabled': enabled,
            'scheduler': 'fsrs' if enabled else 'sm2',
        }


    def chatReviewGeneration(self):
        collection = self.collection()
        profile = self.window().pm.name
        return '{}|{}'.format(profile, os.path.realpath(collection.path))


    def chatReviewGenerationHash(self):
        generation = self.chatReviewGeneration().encode('utf-8')
        return hashlib.sha256(generation).hexdigest()


    def chatReviewIdentity(self):
        return self.window().pm.name, os.path.realpath(self.collection().path)


    def validateChatReviewIdentity(self, pending):
        profileName, collectionPath = self.chatReviewIdentity()
        if pending['profileName'] != profileName:
            self.chatReviewError('REVIEW_PROFILE_CHANGED', 'the active Anki profile changed')
        if pending['collectionPath'] != collectionPath:
            self.chatReviewError('REVIEW_COLLECTION_CHANGED', 'the active collection changed')


    def cleanupChatReviewRegistry(self):
        now = time.time()
        expiredSessions = [
            sessionId for sessionId, pending in self.chatReviewPending.items()
            if now - pending['createdAt'] > self.CHAT_REVIEW_PENDING_TTL_SECONDS
        ]
        for sessionId in expiredSessions:
            del self.chatReviewPending[sessionId]
            self.chatReviewExpired[sessionId] = now

        expiredTombstones = [
            sessionId for sessionId, expiredAt in self.chatReviewExpired.items()
            if now - expiredAt > self.CHAT_REVIEW_COMPLETED_TTL_SECONDS
        ]
        for sessionId in expiredTombstones:
            del self.chatReviewExpired[sessionId]

        expiredTickets = [
            ticket for ticket, completed in self.chatReviewCompleted.items()
            if now - completed['completedAt'] > self.CHAT_REVIEW_COMPLETED_TTL_SECONDS
        ]
        for ticket in expiredTickets:
            del self.chatReviewCompleted[ticket]

        while len(self.chatReviewCompleted) > self.CHAT_REVIEW_MAX_COMPLETED:
            self.chatReviewCompleted.popitem(last=False)
        while len(self.chatReviewExpired) > self.CHAT_REVIEW_MAX_COMPLETED:
            self.chatReviewExpired.popitem(last=False)

        self.chatReviewStatusObserved = {
            ownerHash: observedAt
            for ownerHash, observedAt in self.chatReviewStatusObserved.items()
            if now - observedAt <= 60
        }


    def chatReviewCardData(self, card):
        model = card.note_type()
        return {
            'cardId': card.id,
            'front': util.cardQuestion(card),
            'back': util.cardAnswer(card),
            'deckName': self.deckNameFromId(card.did),
            'modelName': model['name'],
            'due': card.due,
            'interval': card.ivl,
            'factor': card.factor,
        }


    def chatReviewQueueTotal(self, queued, includeLearning, includeNew):
        return (
            queued.review_count
            + (queued.learning_count if includeLearning else 0)
            + (queued.new_count if includeNew else 0)
        )


    def chatReviewCreatePending(self, sessionId, deckName, includeLearning, includeNew):
        if len(self.chatReviewPending) >= self.CHAT_REVIEW_MAX_PENDING:
            self.chatReviewError('REVIEW_SESSION_BUSY', 'pending review session limit reached')

        collection = self.collection()
        if deckName:
            deck = collection.decks.by_name(deckName)
            if deck is None:
                raise Exception('deck was not found: {}'.format(deckName))
            collection.decks.select(deck['id'])

        queued = self.scheduler().get_queued_cards(fetch_limit=1)
        total = self.chatReviewQueueTotal(queued, includeLearning, includeNew)
        if not queued.cards:
            return {
                'success': True,
                'ticket': None,
                'card': None,
                'total': total,
            }

        top = queued.cards[0]
        if top.queue == queued.LEARNING and not includeLearning:
            return {'success': True, 'ticket': None, 'card': None, 'total': total}
        if top.queue == queued.NEW and not includeNew:
            return {'success': True, 'ticket': None, 'card': None, 'total': total}

        card = Card(collection, backend_card=top.card)
        card.start_timer()
        # SchedulingStates is an opaque scheduler-owned protobuf. Preserve the
        # exact Anki-generated alternatives; never derive intervals or FSRS
        # memory state in the ticket layer.
        states = type(top.states)()
        states.CopyFrom(top.states)
        ticket = str(uuid.uuid4())
        response = {
            'success': True,
            'ticket': ticket,
            'card': self.chatReviewCardData(card),
            'total': total,
        }
        profileName, collectionPath = self.chatReviewIdentity()
        self.chatReviewPending[sessionId] = {
            'ticket': ticket,
            'sessionId': sessionId,
            'cardId': card.id,
            'card': card,
            'states': states,
            'deckName': deckName,
            'includeLearning': includeLearning,
            'includeNew': includeNew,
            'createdAt': time.time(),
            'generation': self.chatReviewGeneration(),
            'profileName': profileName,
            'collectionPath': collectionPath,
            'response': response,
        }
        return response


    def advance(self):
        self.server.advance()


    def handler(self, request):
        self.logEvent('request', request)

        name = request.get('action', '')
        version = request.get('version', 4)
        params = request.get('params', {})
        key = request.get('key')

        try:
            if key != util.setting('apiKey') and name != 'requestPermission':
                raise Exception('valid api key must be provided')

            method = None

            for methodName, methodInst in inspect.getmembers(self, predicate=inspect.ismethod):
                apiVersionLast = 0
                apiNameLast = None

                if getattr(methodInst, 'api', False):
                    for apiVersion, apiName in getattr(methodInst, 'versions', []):
                        if apiVersionLast < apiVersion <= version:
                            apiVersionLast = apiVersion
                            apiNameLast = apiName

                    if apiNameLast is None and apiVersionLast == 0:
                        apiNameLast = methodName

                    if apiNameLast is not None and apiNameLast == name:
                        method = methodInst
                        break

            if method is None:
                raise Exception('unsupported action')

            api_return_value = methodInst(**params)
            reply = format_success_reply(version, api_return_value)

        except Exception as e:
            reply = format_exception_reply(version, e)

        self.logEvent('reply', reply)
        return reply


    def window(self):
        return aqt.mw


    def reviewer(self):
        reviewer = self.window().reviewer
        if reviewer is None:
            raise Exception('reviewer is not available')

        return reviewer


    def collection(self):
        collection = self.window().col
        if collection is None:
            raise Exception('collection is not available')

        return collection


    def decks(self):
        decks = self.collection().decks
        if decks is None:
            raise Exception('decks are not available')

        return decks


    def scheduler(self):
        scheduler = self.collection().sched
        if scheduler is None:
            raise Exception('scheduler is not available')

        return scheduler


    def database(self):
        database = self.collection().db
        if database is None:
            raise Exception('database is not available')

        return database


    def media(self):
        media = self.collection().media
        if media is None:
            raise Exception('media is not available')

        return media


    def getModel(self, modelName):
        model = self.collection().models.by_name(modelName)
        if model is None:
            raise Exception('model was not found: {}'.format(modelName))
        return model


    def getField(self, model, fieldName):
        fieldMap = self.collection().models.field_map(model)
        if fieldName not in fieldMap:
            raise Exception('field was not found in {}: {}'.format(model['name'], fieldName))
        return fieldMap[fieldName][1]


    def getTemplate(self, model, templateName):
        for ankiTemplate in model['tmpls']:
            if ankiTemplate['name'] == templateName:
                return ankiTemplate
        raise Exception('template was not found in {}: {}'.format(model['name'], templateName))


    def startEditing(self):
        self.window().requireReset()


    def createNote(self, note):
        collection = self.collection()

        model = collection.models.by_name(note['modelName'])
        if model is None:
            raise Exception('model was not found: {}'.format(note['modelName']))

        deck = collection.decks.by_name(note['deckName'])
        if deck is None:
            raise Exception('deck was not found: {}'.format(note['deckName']))

        ankiNote = anki.notes.Note(collection, model)
        ankiNote.note_type()['did'] = deck['id']
        if 'tags' in note:
            ankiNote.tags = note['tags']

        for name, value in note['fields'].items():
            for ankiName in ankiNote.keys():
                if name.lower() == ankiName.lower():
                    ankiNote[ankiName] = value
                    break

        self.addMediaFromNote(ankiNote, note)

        allowDuplicate = False
        duplicateScope = None
        duplicateScopeDeckName = None
        duplicateScopeCheckChildren = False
        duplicateScopeCheckAllModels = False

        if 'options' in note:
            options = note['options']
            if 'allowDuplicate' in options:
                allowDuplicate = options['allowDuplicate']
                if type(allowDuplicate) is not bool:
                    raise Exception('option parameter "allowDuplicate" must be boolean')
            if 'duplicateScope' in options:
                duplicateScope = options['duplicateScope']
            if 'duplicateScopeOptions' in options:
                duplicateScopeOptions = options['duplicateScopeOptions']
                if 'deckName' in duplicateScopeOptions:
                    duplicateScopeDeckName = duplicateScopeOptions['deckName']
                if 'checkChildren' in duplicateScopeOptions:
                    duplicateScopeCheckChildren = duplicateScopeOptions['checkChildren']
                    if type(duplicateScopeCheckChildren) is not bool:
                        raise Exception('option parameter "duplicateScopeOptions.checkChildren" must be boolean')
                if 'checkAllModels' in duplicateScopeOptions:
                    duplicateScopeCheckAllModels = duplicateScopeOptions['checkAllModels']
                    if type(duplicateScopeCheckAllModels) is not bool:
                        raise Exception('option parameter "duplicateScopeOptions.checkAllModels" must be boolean')

        duplicateOrEmpty = self.isNoteDuplicateOrEmptyInScope(
            ankiNote,
            deck,
            collection,
            duplicateScope,
            duplicateScopeDeckName,
            duplicateScopeCheckChildren,
            duplicateScopeCheckAllModels
        )

        if duplicateOrEmpty == 1:
            raise Exception('cannot create note because it is empty')
        elif duplicateOrEmpty == 2:
            if allowDuplicate:
                return ankiNote
            raise Exception('cannot create note because it is a duplicate')
        elif duplicateOrEmpty == 0:
            return ankiNote
        else:
            raise Exception('cannot create note for unknown reason')


    def isNoteDuplicateOrEmptyInScope(
        self,
        note,
        deck,
        collection,
        duplicateScope,
        duplicateScopeDeckName,
        duplicateScopeCheckChildren,
        duplicateScopeCheckAllModels
    ):
        # Returns: 1 if first is empty, 2 if first is a duplicate, 0 otherwise.

        # note.dupeOrEmpty returns if a note is a global duplicate with the specific model.
        # This is used as the default check, and the rest of this function is manually
        # checking if the note is a duplicate with additional options.
        if duplicateScope != 'deck' and not duplicateScopeCheckAllModels:
            return note.dupeOrEmpty() or 0

        # Primary field for uniqueness
        val = note.fields[0]
        if not val.strip():
            return 1
        csum = anki.utils.field_checksum(val)

        # Create dictionary of deck ids
        dids = None
        if duplicateScope == 'deck':
            did = deck['id']
            if duplicateScopeDeckName is not None:
                deck2 = collection.decks.by_name(duplicateScopeDeckName)
                if deck2 is None:
                    # Invalid deck, so cannot be duplicate
                    return 0
                did = deck2['id']

            dids = {did: True}
            if duplicateScopeCheckChildren:
                for kv in collection.decks.children(did):
                    dids[kv[1]] = True

        # Build query
        query = 'select id from notes where csum=?'
        queryArgs = [csum]
        if note.id:
            query += ' and id!=?'
            queryArgs.append(note.id)
        if not duplicateScopeCheckAllModels:
            query += ' and mid=?'
            queryArgs.append(note.mid)

        # Search
        for noteId in note.col.db.list(query, *queryArgs):
            if dids is None:
                # Duplicate note exists in the collection
                return 2
            # Validate that a card exists in one of the specified decks
            for cardDeckId in note.col.db.list('select did from cards where nid=?', noteId):
                if cardDeckId in dids:
                    return 2

        # Not a duplicate
        return 0

    def raiseNotFoundError(self, errorMsg):
        if anki_version < (2, 1, 55):
            raise NotFoundError(errorMsg)
        raise NotFoundError(errorMsg, None, None, None)

    def getCard(self, card_id: int) -> Card:
        try:
            return self.collection().get_card(card_id)
        except NotFoundError:
            self.raiseNotFoundError('Card was not found: {}'.format(card_id))

    def getNote(self, note_id: int) -> Note:
        try:
            return self.collection().get_note(note_id)
        except NotFoundError:
            self.raiseNotFoundError('Note was not found: {}'.format(note_id))

    def deckStatsToJson(self, due_tree):
        deckStats = {'deck_id': due_tree.deck_id,
                     'name': due_tree.name,
                     'new_count': due_tree.new_count,
                     'learn_count': due_tree.learn_count,
                     'review_count': due_tree.review_count}
        if anki_version > (2, 1, 46):
            # total_in_deck is not supported on lower Anki versions
            deckStats['total_in_deck'] = due_tree.total_in_deck
        return deckStats

    def collectDeckTreeChildren(self, parent_node):
        allNodes = {parent_node.deck_id: parent_node}
        for child in parent_node.children:
            for deckId, childNode in self.collectDeckTreeChildren(child).items():
                allNodes[deckId] = childNode
        return allNodes

    #
    # Miscellaneous
    #

    @util.api()
    def version(self):
        return util.setting('apiVersion')


    @util.api()
    def requestPermission(self, origin, allowed):
        results = {
                "permission": "denied",
        }

        if allowed:
            results = {
                    "permission": "granted",
                    "requireApikey": bool(util.setting('apiKey')),
                    "version": util.setting('apiVersion')
            }

        elif origin in util.setting('ignoreOriginList'):
            pass  # defaults to denied

        else:  # prompt the user
            msg = QMessageBox(None)
            msg.setWindowTitle("A website wants to access to Anki")
            msg.setText('"{}" requests permission to use Anki through AnkiConnect. Do you want to give it access?'.format(origin))
            msg.setInformativeText("By granting permission, you'll allow the website to modify your collection on your behalf, including the execution of destructive actions such as deck deletion.")
            msg.setWindowIcon(self.window().windowIcon())
            msg.setIcon(QMessageBox.Icon.Question)
            msg.setStandardButtons(QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No)
            msg.setDefaultButton(QMessageBox.StandardButton.No)
            msg.setCheckBox(QCheckBox(text='Ignore further requests from "{}"'.format(origin), parent=msg))
            if hasattr(Qt, 'WindowStaysOnTopHint'):
                # Qt5
                WindowOnTopFlag = Qt.WindowStaysOnTopHint
            elif hasattr(Qt, 'WindowType') and hasattr(Qt.WindowType, 'WindowStaysOnTopHint'):
                # Qt6
                WindowOnTopFlag = Qt.WindowType.WindowStaysOnTopHint
            msg.setWindowFlags(WindowOnTopFlag)
            pressedButton = msg.exec()

            if pressedButton == QMessageBox.StandardButton.Yes:
                config = aqt.mw.addonManager.getConfig(__name__)
                config["webCorsOriginList"] = util.setting('webCorsOriginList')
                config["webCorsOriginList"].append(origin)
                aqt.mw.addonManager.writeConfig(__name__, config)
                results = {
                    "permission": "granted",
                    "requireApikey": bool(util.setting('apiKey')),
                    "version": util.setting('apiVersion')
                }

            # if the origin isn't an empty string, the user clicks "No", and the ignore box is checked
            elif origin and pressedButton == QMessageBox.StandardButton.No and msg.checkBox().isChecked():
                config = aqt.mw.addonManager.getConfig(__name__)
                config["ignoreOriginList"] = util.setting('ignoreOriginList')
                config["ignoreOriginList"].append(origin)
                aqt.mw.addonManager.writeConfig(__name__, config)

            # else defaults to denied

        return results


    @util.api()
    def getProfiles(self):
        return self.window().pm.profiles()
    
    @util.api()
    def getActiveProfile(self):
        return self.window().pm.name

    @util.api()
    def loadProfile(self, name):
        if name not in self.window().pm.profiles():
            return False

        if self.window().isVisible():
            cur_profile = self.window().pm.name
            if cur_profile != name:
                self.window().unloadProfileAndShowProfileManager()

                def waiter():
                    # This function waits until main window is closed
                    # It's needed cause sync can take quite some time
                    # And if we call loadProfile until sync is ended things will go wrong
                    if self.window().isVisible():
                        QTimer.singleShot(1000, waiter)
                    else:
                        self.loadProfile(name)

                waiter()
        else:
            self.window().pm.load(name)
            self.window().loadProfile()
            self.window().profileDiag.closeWithoutQuitting()

        return True


    @util.api()
    def sync(self):
        mw = self.window()
        auth = mw.pm.sync_auth()
        if not auth:
            raise Exception("sync: auth not configured")
        out = mw.col.sync_collection(auth, mw.pm.media_syncing_enabled())
        accepted_sync_statuses = [out.NO_CHANGES, out.NORMAL_SYNC]
        if out.required not in accepted_sync_statuses:
            raise Exception(f"Sync status {out.required} not one of {accepted_sync_statuses} - see SyncCollectionResponse.ChangesRequired for list of sync statuses: https://github.com/ankitects/anki/blob/e41c4573d789afe8b020fab5d9d1eede50c3fa3d/proto/anki/sync.proto#L57-L65")
        mw.onSync()


    @util.api()
    def multi(self, actions):
        return list(map(self.handler, actions))


    @util.api()
    def getNumCardsReviewedToday(self):
        return self.database().scalar('select count() from revlog where id > ?', (self.scheduler().dayCutoff - 86400) * 1000)

    @util.api()
    def getNumCardsReviewedByDay(self):
        return self.database().all('select date(id/1000 - ?, "unixepoch", "localtime") as day, count() from revlog group by day order by day desc',
                                    int(time.strftime("%H", time.localtime(self.scheduler().dayCutoff))) * 3600)


    @util.api()
    def getCollectionStatsHTML(self, wholeCollection=True):
        stats = self.collection().stats()
        stats.wholeCollection = wholeCollection
        return stats.report()


    #
    # Decks
    #

    @util.api()
    def deckNames(self):
        return [x.name for x in self.decks().all_names_and_ids()]


    @util.api()
    def deckNamesAndIds(self):
        decks = {}
        for deck in self.deckNames():
            decks[deck] = self.decks().id(deck)

        return decks


    @util.api()
    def getDecks(self, cards):
        decks = {}
        for card in cards:
            did = self.database().scalar('select did from cards where id=?', card)
            deck = self.decks().get(did)['name']
            if deck in decks:
                decks[deck].append(card)
            else:
                decks[deck] = [card]

        return decks


    @util.api()
    def createDeck(self, deck):
        self.startEditing()
        return  self.decks().id(deck)


    @util.api()
    def changeDeck(self, cards, deck):
        self.startEditing()

        did = self.collection().decks.id(deck)
        mod = anki.utils.int_time()
        usn = self.collection().usn()

        # normal cards
        scids = anki.utils.ids2str(cards)
        # remove any cards from filtered deck first
        self.collection().sched.remFromDyn(cards)

        # then move into new deck
        self.collection().db.execute('update cards set usn=?, mod=?, did=? where id in ' + scids, usn, mod, did)


    @util.api()
    def deleteDecks(self, decks, cardsToo=False):
        if not cardsToo:
            # since f592672fa952260655881a75a2e3c921b2e23857 (2.1.28)
            # (see anki$ git log "-Gassert cardsToo")
            # you can't delete decks without deleting cards as well.
            # however, since 62c23c6816adf912776b9378c008a52bb50b2e8d (2.1.45)
            # passing cardsToo to `rem` (long deprecated) won't raise an error!
            # this is dangerous, so let's raise our own exception
            raise Exception("Since Anki 2.1.28 it's not possible "
                            "to delete decks without deleting cards as well")
        self.startEditing()
        decks = filter(lambda d: d in self.deckNames(), decks)
        for deck in decks:
            did = self.decks().id(deck)
            self.decks().remove([did])


    @util.api()
    def getDeckConfig(self, deck):
        if deck not in self.deckNames():
            return False

        collection = self.collection()
        did = collection.decks.id(deck)
        return collection.decks.config_dict_for_deck_id(did)


    @util.api()
    def saveDeckConfig(self, config):
        collection = self.collection()

        config['id'] = str(config['id'])
        config['mod'] = anki.utils.int_time()
        config['usn'] = collection.usn()
        if int(config['id']) not in [c['id'] for c in collection.decks.all_config()]:
            return False
        try:
            collection.decks.save(config)
            collection.decks.update_config(config)
        except:
            return False
        return True


    @util.api()
    def setDeckConfigId(self, decks, configId):
        configId = int(configId)
        for deck in decks:
            if not deck in self.deckNames():
                return False

        collection = self.collection()

        for deck in decks:
            try:
                did = str(collection.decks.id(deck))
                deck_dict = aqt.mw.col.decks.decks[did]
                deck_dict['conf'] = configId
                collection.decks.save(deck_dict)
            except:
                return False

        return True


    @util.api()
    def cloneDeckConfigId(self, name, cloneFrom='1'):
        configId = int(cloneFrom)
        collection = self.collection()
        if configId not in [c['id'] for c in collection.decks.all_config()]:
            return False

        config = collection.decks.get_config(configId)
        return collection.decks.add_config_returning_id(name, config)


    @util.api()
    def removeDeckConfigId(self, configId):
        collection = self.collection()
        if int(configId) not in [c['id'] for c in collection.decks.all_config()]:
            return False

        collection.decks.remove_config(configId)
        return True

    @util.api()
    def getDeckStats(self, decks):
        collection = self.collection()
        scheduler = self.scheduler()
        responseDict = {}
        deckIds = list(map(lambda d: collection.decks.id(d), decks))

        allDeckNodes = self.collectDeckTreeChildren(scheduler.deck_due_tree())
        for deckId, deckNode in allDeckNodes.items():
            if deckId in deckIds:
                responseDict[deckId] = self.deckStatsToJson(deckNode)
        return responseDict

    @util.api()
    def storeMediaFile(self, filename, data=None, path=None, url=None, skipHash=None, deleteExisting=True):
        if not (data or path or url):
            raise Exception('You must provide a "data", "path", or "url" field.')
        if data:
            mediaData = base64.b64decode(data)
        elif path:
            with open(path, 'rb') as f:
                mediaData = f.read()
        elif url:
            mediaData = util.download(url)

        if skipHash is None:
            skip = False
        else:
            m = hashlib.md5()
            m.update(mediaData)
            skip = skipHash == m.hexdigest()

        if skip:
            return None
        if deleteExisting:
            self.deleteMediaFile(filename)
        return self.media().writeData(filename, mediaData)


    @util.api()
    def retrieveMediaFile(self, filename):
        filename = os.path.basename(filename)
        filename = unicodedata.normalize('NFC', filename)
        filename = self.media().stripIllegal(filename)

        path = os.path.join(self.media().dir(), filename)
        if os.path.exists(path):
            with open(path, 'rb') as file:
                return base64.b64encode(file.read()).decode('ascii')

        return False


    @util.api()
    def getMediaFilesNames(self, pattern='*'):
        path = os.path.join(self.media().dir(), pattern)
        return [os.path.basename(p) for p in glob.glob(path)]


    @util.api()
    def deleteMediaFile(self, filename):
        self.media().trash_files([filename])

    @util.api()
    def getMediaDirPath(self):
        return os.path.abspath(self.media().dir())

    @util.api()
    def addNote(self, note):
        self.startEditing()
        ankiNote = self.createNote(note)

        collection = self.collection()
        nCardsAdded = collection.addNote(ankiNote)
        if nCardsAdded < 1:
            raise Exception('The field values you have provided would make an empty question on all cards.')

        return ankiNote.id


    def addMediaFromNote(self, ankiNote, note):
        audioObjectOrList = note.get('audio')
        self.addMedia(ankiNote, audioObjectOrList, util.MediaType.Audio)

        videoObjectOrList = note.get('video')
        self.addMedia(ankiNote, videoObjectOrList, util.MediaType.Video)

        pictureObjectOrList = note.get('picture')
        self.addMedia(ankiNote, pictureObjectOrList, util.MediaType.Picture)



    def addMedia(self, ankiNote, mediaObjectOrList, mediaType):
        if mediaObjectOrList is None:
            return

        if isinstance(mediaObjectOrList, list):
            mediaList = mediaObjectOrList
        else:
            mediaList = [mediaObjectOrList]

        for media in mediaList:
            if media is not None:
                try:
                    mediaFilename = self.storeMediaFile(media['filename'],
                                                        data=media.get('data'),
                                                        path=media.get('path'),
                                                        url=media.get('url'),
                                                        skipHash=media.get('skipHash'),
                                                        deleteExisting=media.get('deleteExisting'))

                    if mediaFilename is not None and 'fields' in media and type(media['fields']) == list:
                        for field in media['fields']:
                            if field in ankiNote:
                                if mediaType is util.MediaType.Picture:
                                    ankiNote[field] += u'<img src="{}">'.format(mediaFilename)
                                elif mediaType is util.MediaType.Audio or mediaType is util.MediaType.Video:
                                    ankiNote[field] += u'[sound:{}]'.format(mediaFilename)

                except Exception as e:
                    errorMessage = str(e).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                    for field in media['fields']:
                        if field in ankiNote:
                            ankiNote[field] += errorMessage


    @util.api()
    def canAddNote(self, note):
        try:
            return bool(self.createNote(note))
        except:
            return False

    @util.api()
    def canAddNoteWithErrorDetail(self, note):
        try:
            return {
                'canAdd': bool(self.createNote(note))
            }
        except Exception as e:
            return {
                'canAdd': False,
                'error': str(e)
            }

    @util.api()
    def updateNoteFields(self, note):
        ankiNote = self.getNote(note['id'])

        self.startEditing()
        for name, value in note['fields'].items():
            if name in ankiNote:
                ankiNote[name] = value

        self.addMediaFromNote(ankiNote, note)

        self.collection().update_note(ankiNote, skip_undo_entry=True);


    @util.api()
    def updateNote(self, note):
        updated = False
        if 'fields' in note.keys():
            self.updateNoteFields(note)
            updated = True
        if 'tags' in note.keys():
            self.updateNoteTags(note['id'], note['tags'])
            updated = True
        if not updated:
            raise Exception('Must provide a "fields" or "tags" property.')

    @util.api()
    def updateNoteModel(self, note):
        """
        Update the model and fields of a given note.

        :param note: A dictionary containing note details, including 'id', 'modelName', 'fields', and 'tags'.
        """
        # Extract and validate the note ID
        note_id = note.get('id')
        if not note_id:
            raise ValueError("Note ID is required")

        # Extract and validate the new model name
        new_model_name = note.get('modelName')
        if not new_model_name:
            raise ValueError("Model name is required")

        # Extract and validate the new fields
        new_fields = note.get('fields')
        if not new_fields or not isinstance(new_fields, dict):
            raise ValueError("Fields must be provided as a dictionary")

        # Extract the new tags
        new_tags = note.get('tags', [])

        # Get the current note from the collection
        anki_note = self.getNote(note_id)

        # Get the new model from the collection
        collection = self.collection()
        new_model = collection.models.by_name(new_model_name)
        if not new_model:
            raise ValueError(f"Model '{new_model_name}' not found")

        # Update the note's model
        anki_note.mid = new_model['id']
        anki_note._fmap = collection.models.field_map(new_model)
        anki_note.fields = [''] * len(new_model['flds'])

        # Update the fields with new values
        for name, value in new_fields.items():
            for anki_name in anki_note.keys():
                if name.lower() == anki_name.lower():
                    anki_note[anki_name] = value
                    break

        # Update the tags
        anki_note.tags = new_tags

        # Update note to ensure changes are saved
        collection.update_note(anki_note, skip_undo_entry=True);

    @util.api()
    def updateNoteTags(self, note, tags):
        if type(tags) == str:
            tags = [tags]
        if type(tags) != list or not all([type(t) == str for t in tags]):
            raise Exception('Must provide tags as a list of strings')

        for old_tag in self.getNoteTags(note):
            self.removeTags([note], old_tag)
        for new_tag in tags:
            self.addTags([note], new_tag)


    @util.api()
    def getNoteTags(self, note):
        return self.getNote(note).tags


    @util.api()
    def addTags(self, notes, tags, add=True):
        self.startEditing()
        self.collection().tags.bulkAdd(notes, tags, add)


    @util.api()
    def removeTags(self, notes, tags):
        return self.addTags(notes, tags, False)


    @util.api()
    def getTags(self):
        return self.collection().tags.all()


    @util.api()
    def clearUnusedTags(self):
        self.collection().tags.registerNotes()


    @util.api()
    def replaceTags(self, notes, tag_to_replace, replace_with_tag):
        self.window().progress.start()

        for nid in notes:
            try:
                note = self.getNote(nid)
            except NotFoundError:
                continue

            if note.has_tag(tag_to_replace):
                note.remove_tag(tag_to_replace)
                note.add_tag(replace_with_tag)
                self.collection().update_note(note, skip_undo_entry=True);

        self.window().requireReset()
        self.window().progress.finish()
        self.window().reset()


    @util.api()
    def replaceTagsInAllNotes(self, tag_to_replace, replace_with_tag):
        self.window().progress.start()

        collection = self.collection()
        for nid in collection.db.list('select id from notes'):
            note = self.getNote(nid)
            if note.has_tag(tag_to_replace):
                note.remove_tag(tag_to_replace)
                note.add_tag(replace_with_tag)
                self.collection().update_note(note, skip_undo_entry=True);

        self.window().requireReset()
        self.window().progress.finish()
        self.window().reset()


    @util.api()
    def setEaseFactors(self, cards, easeFactors):
        couldSetEaseFactors = []
        for i, card in enumerate(cards):
            try:
                ankiCard = self.getCard(card)
            except NotFoundError:
                couldSetEaseFactors.append(False)
                continue

            couldSetEaseFactors.append(True)
            ankiCard.factor = easeFactors[i]
            self.collection().update_card(ankiCard, skip_undo_entry=True)

        return couldSetEaseFactors

    @util.api()
    def setSpecificValueOfCard(self, card, keys,
                               newValues, warning_check=False):
        if isinstance(card, list):
            print("card has to be int, not list")
            return False

        if not isinstance(keys, list) or not isinstance(newValues, list):
            print("keys and newValues have to be lists.")
            return False

        if len(newValues) != len(keys):
            print("Invalid list lengths.")
            return False

        for key in keys:
            if key in ["did", "id", "ivl", "lapses", "left", "mod", "nid",
                       "odid", "odue", "ord", "queue", "reps", "type", "usn"]:
                if warning_check is False:
                    return False

        result = []
        try:
            ankiCard = self.getCard(card)
            for i, key in enumerate(keys):
                setattr(ankiCard, key, newValues[i])
            self.collection().update_card(ankiCard, skip_undo_entry=True)
            result.append(True)
        except Exception as e:
            result.append([False, str(e)])
        return result


    @util.api()
    def getEaseFactors(self, cards):
        easeFactors = []
        for card in cards:
            try:
                ankiCard = self.getCard(card)
            except NotFoundError:
                easeFactors.append(None)
                continue

            easeFactors.append(ankiCard.factor)

        return easeFactors


    @util.api()
    def suspend(self, cards, suspend=True):
        for card in cards:
            if self.suspended(card) == suspend:
                cards.remove(card)

        if len(cards) == 0:
            return False

        scheduler = self.scheduler()
        self.startEditing()
        if suspend:
            scheduler.suspendCards(cards)
        else:
            scheduler.unsuspendCards(cards)

        return True


    @util.api()
    def unsuspend(self, cards):
        self.suspend(cards, False)


    @util.api()
    def suspended(self, card):
        card = self.getCard(card)
        return card.queue == -1


    @util.api()
    def areSuspended(self, cards):
        suspended = []
        for card in cards:
            try:
                suspended.append(self.suspended(card))
            except NotFoundError:
                suspended.append(None)

        return suspended


    @util.api()
    def areDue(self, cards):
        due = []
        for card in cards:
            if self.findCards('cid:{} is:new'.format(card)):
                due.append(True)
            else:
                date, ivl = self.collection().db.all('select id/1000.0, ivl from revlog where cid = ?', card)[-1]
                if ivl >= -1200:
                    due.append(bool(self.findCards('cid:{} is:due'.format(card))))
                else:
                    due.append(date - ivl <= time.time())

        return due


    @util.api()
    def getIntervals(self, cards, complete=False):
        intervals = []
        for card in cards:
            if self.findCards('cid:{} is:new'.format(card)):
                intervals.append(0)
            else:
                interval = self.collection().db.list('select ivl from revlog where cid = ?', card)
                if not complete:
                    interval = interval[-1]
                intervals.append(interval)

        return intervals



    @util.api()
    def modelNames(self):
        return [n.name for n in self.collection().models.all_names_and_ids()]


    @util.api()
    def createModel(self, modelName, inOrderFields, cardTemplates, css = None, isCloze = False):
        # https://github.com/dae/anki/blob/b06b70f7214fb1f2ce33ba06d2b095384b81f874/anki/stdmodels.py
        if len(inOrderFields) == 0:
            raise Exception('Must provide at least one field for inOrderFields')
        if len(cardTemplates) == 0:
            raise Exception('Must provide at least one card for cardTemplates')
        if modelName in [n.name for n in self.collection().models.all_names_and_ids()]:
            raise Exception('Model name already exists')

        collection = self.collection()
        mm = collection.models

        # Generate new Note
        m = mm.new(modelName)
        if isCloze:
            m['type'] = MODEL_CLOZE

        # Create fields and add them to Note
        for field in inOrderFields:
            fm = mm.new_field(field)
            mm.addField(m, fm)

        # Add shared css to model if exists. Use default otherwise
        if (css is not None):
            m['css'] = css

        # Generate new card template(s)
        cardCount = 1
        for card in cardTemplates:
            cardName = 'Card ' + str(cardCount)
            if 'Name' in card:
                cardName = card['Name']

            t = mm.new_template(cardName)
            cardCount += 1
            t['qfmt'] = card['Front']
            t['afmt'] = card['Back']
            mm.addTemplate(m, t)

        mm.add(m)
        return m


    @util.api()
    def modelNamesAndIds(self):
        models = {}
        for model in self.modelNames():
            models[model] = int(self.collection().models.by_name(model)['id'])

        return models


    @util.api()
    def findModelsById(self, modelIds):
        models = []
        for id in modelIds:
            model = self.collection().models.get(id)
            if model is None:
                raise Exception("model was not found: {}".format(id))
            else:
                models.append(model)
        return models

    @util.api()
    def findModelsByName(self, modelNames):
        models = []
        for name in modelNames:
            model = self.collection().models.by_name(name)
            if model is None:
                raise Exception("model was not found: {}".format(name))
            else:
                models.append(model)
        return models

    @util.api()
    def modelNameFromId(self, modelId):
        model = self.collection().models.get(modelId)
        if model is None:
            raise Exception('model was not found: {}'.format(modelId))
        else:
            return model['name']


    @util.api()
    def modelFieldNames(self, modelName):
        model = self.collection().models.by_name(modelName)
        if model is None:
            raise Exception('model was not found: {}'.format(modelName))
        else:
            return [field['name'] for field in model['flds']]


    @util.api()
    def modelFieldDescriptions(self, modelName):
        model = self.collection().models.by_name(modelName)
        if model is None:
            raise Exception('model was not found: {}'.format(modelName))
        else:
            try:
                return [field['description'] for field in model['flds']]
            except KeyError:
                # older versions of Anki don't have field descriptions
                return ['' for field in model['flds']]


    @util.api()
    def modelFieldFonts(self, modelName):
        model = self.getModel(modelName)

        fonts = {}
        for field in model['flds']:

            fonts[field['name']] = {
                'font': field['font'],
                'size': field['size'],
            }

        return fonts


    @util.api()
    def modelFieldsOnTemplates(self, modelName):
        model = self.collection().models.by_name(modelName)
        if model is None:
            raise Exception('model was not found: {}'.format(modelName))

        templates = {}
        for template in model['tmpls']:
            fields = []
            for side in ['qfmt', 'afmt']:
                fieldsForSide = []

                # based on _fieldsOnTemplate from aqt/clayout.py
                matches = re.findall('{{[^#/}]+?}}', template[side])
                for match in matches:
                    # remove braces and modifiers
                    match = re.sub(r'[{}]', '', match)
                    match = match.split(':')[-1]

                    # for the answer side, ignore fields present on the question side + the FrontSide field
                    if match == 'FrontSide' or side == 'afmt' and match in fields[0]:
                        continue
                    fieldsForSide.append(match)

                fields.append(fieldsForSide)

            templates[template['name']] = fields

        return templates


    @util.api()
    def modelTemplates(self, modelName):
        model = self.collection().models.by_name(modelName)
        if model is None:
            raise Exception('model was not found: {}'.format(modelName))

        templates = {}
        for template in model['tmpls']:
            templates[template['name']] = {'Front': template['qfmt'], 'Back': template['afmt']}

        return templates


    @util.api()
    def modelStyling(self, modelName):
        model = self.collection().models.by_name(modelName)
        if model is None:
            raise Exception('model was not found: {}'.format(modelName))

        return {'css': model['css']}


    @util.api()
    def updateModelTemplates(self, model):
        models = self.collection().models
        ankiModel = models.by_name(model['name'])
        if ankiModel is None:
            raise Exception('model was not found: {}'.format(model['name']))

        templates = model['templates']
        for ankiTemplate in ankiModel['tmpls']:
            template = templates.get(ankiTemplate['name'])
            if template:
                qfmt = template.get('Front')
                if qfmt:
                    ankiTemplate['qfmt'] = qfmt

                afmt = template.get('Back')
                if afmt:
                    ankiTemplate['afmt'] = afmt

        self.save_model(models, ankiModel)


    @util.api()
    def updateModelStyling(self, model):
        models = self.collection().models
        ankiModel = models.by_name(model['name'])
        if ankiModel is None:
            raise Exception('model was not found: {}'.format(model['name']))

        ankiModel['css'] = model['css']

        self.save_model(models, ankiModel)


    @util.api()
    def findAndReplaceInModels(self, modelName, findText, replaceText, front=True, back=True, css=True):
        if not modelName:
            ankiModel = self.collection().models.allNames()
        else:
            model = self.collection().models.by_name(modelName)
            if model is None:
                raise Exception('model was not found: {}'.format(modelName))
            ankiModel = [modelName]
        updatedModels = 0
        for model in ankiModel:
            model = self.collection().models.by_name(model)
            checkForText = False
            if css and findText in model['css']:
                checkForText = True
                model['css'] = model['css'].replace(findText, replaceText)
            for tmpls in model.get('tmpls'):
                if front and findText in tmpls['qfmt']:
                    checkForText = True
                    tmpls['qfmt'] = tmpls['qfmt'].replace(findText, replaceText)
                if back and findText in tmpls['afmt']:
                    checkForText = True
                    tmpls['afmt'] = tmpls['afmt'].replace(findText, replaceText)
            self.save_model(self.collection().models, model)
            if checkForText:
                updatedModels += 1
        return updatedModels


    @util.api()
    def modelTemplateRename(self, modelName, oldTemplateName, newTemplateName):
        mm = self.collection().models
        model = self.getModel(modelName)
        ankiTemplate = self.getTemplate(model, oldTemplateName)

        ankiTemplate['name'] = newTemplateName
        self.save_model(mm, model)


    @util.api()
    def modelTemplateReposition(self, modelName, templateName, index):
        mm = self.collection().models
        model = self.getModel(modelName)
        ankiTemplate = self.getTemplate(model, templateName)

        mm.reposition_template(model, ankiTemplate, index)
        self.save_model(mm, model)


    @util.api()
    def modelTemplateAdd(self, modelName, template):
        # "Name", "Front", "Back" borrows from `createModel`
        mm = self.collection().models
        model = self.getModel(modelName)
        name = template['Name']
        qfmt = template['Front']
        afmt = template['Back']

        # updates the template if it already exists
        for ankiTemplate in model['tmpls']:
            if ankiTemplate['name'] == name:
                ankiTemplate['qfmt'] = qfmt
                ankiTemplate['afmt'] = afmt
                return

        ankiTemplate = mm.new_template(name)
        ankiTemplate['qfmt'] = qfmt
        ankiTemplate['afmt'] = afmt
        mm.add_template(model, ankiTemplate)

        self.save_model(mm, model)


    @util.api()
    def modelTemplateRemove(self, modelName, templateName):
        mm = self.collection().models
        model = self.getModel(modelName)
        ankiTemplate = self.getTemplate(model, templateName)

        mm.remove_template(model, ankiTemplate)
        self.save_model(mm, model)


    @util.api()
    def modelFieldRename(self, modelName, oldFieldName, newFieldName):
        mm = self.collection().models
        model = self.getModel(modelName)
        field = self.getField(model, oldFieldName)

        mm.renameField(model, field, newFieldName)

        self.save_model(mm, model)


    @util.api()
    def modelFieldReposition(self, modelName, fieldName, index):
        mm = self.collection().models
        model = self.getModel(modelName)
        field = self.getField(model, fieldName)

        mm.reposition_field(model, field, index)

        self.save_model(mm, model)


    @util.api()
    def modelFieldAdd(self, modelName, fieldName, index=None):
        mm = self.collection().models
        model = self.getModel(modelName)

        # only adds the field if it doesn't already exist
        fieldMap = mm.field_map(model)
        if fieldName not in fieldMap:
            field = mm.new_field(fieldName)
            mm.addField(model, field)

        # repositions, even if the field already exists
        if index is not None:
            fieldMap = mm.field_map(model)
            newField = fieldMap[fieldName][1]
            mm.reposition_field(model, newField, index)

        self.save_model(mm, model)


    @util.api()
    def modelFieldRemove(self, modelName, fieldName):
        mm = self.collection().models
        model = self.getModel(modelName)
        field = self.getField(model, fieldName)

        mm.remove_field(model, field)

        self.save_model(mm, model)


    @util.api()
    def modelFieldSetFont(self, modelName, fieldName, font):
        mm = self.collection().models
        model = self.getModel(modelName)
        field = self.getField(model, fieldName)

        if not isinstance(font, str):
            raise Exception('font should be a string: {}'.format(font))

        field['font'] = font

        self.save_model(mm, model)


    @util.api()
    def modelFieldSetFontSize(self, modelName, fieldName, fontSize):
        mm = self.collection().models
        model = self.getModel(modelName)
        field = self.getField(model, fieldName)

        if not isinstance(fontSize, int):
            raise Exception('fontSize should be an integer: {}'.format(fontSize))

        field['size'] = fontSize

        self.save_model(mm, model)


    @util.api()
    def modelFieldSetDescription(self, modelName, fieldName, description):
        mm = self.collection().models
        model = self.getModel(modelName)
        field = self.getField(model, fieldName)

        if not isinstance(description, str):
            raise Exception('description should be a string: {}'.format(description))

        if 'description' in field: # older versions do not have the 'description' key
            field['description'] = description
            self.save_model(mm, model)
            return True
        return False


    @util.api()
    def deckNameFromId(self, deckId):
        deck = self.collection().decks.get(deckId)
        if deck is None:
            raise Exception('deck was not found: {}'.format(deckId))

        return deck['name']


    @util.api()
    def findNotes(self, query=None):
        if query is None:
            return []

        return list(map(int, self.collection().find_notes(query)))


    @util.api()
    def findCards(self, query=None):
        if query is None:
            return []

        return list(map(int, self.collection().find_cards(query)))


    @util.api()
    def cardsInfo(self, cards):
        result = []
        for cid in cards:
            try:
                card = self.getCard(cid)
                model = card.note_type()
                note = card.note()
                fields = {}
                for info in model['flds']:
                    order = info['ord']
                    name = info['name']
                    fields[name] = {'value': note.fields[order], 'order': order}
                states = self.collection()._backend.get_scheduling_states(card.id)
                nextReviews = self.collection()._backend.describe_next_states(states)

                result.append({
                    'cardId': card.id,
                    'fields': fields,
                    'fieldOrder': card.ord,
                    'question': util.cardQuestion(card),
                    'answer': util.cardAnswer(card),
                    'modelName': model['name'],
                    'ord': card.ord,
                    'deckName': self.deckNameFromId(card.did),
                    'css': model['css'],
                    'factor': card.factor,
                    #This factor is 10 times the ease percentage,
                    # so an ease of 310% would be reported as 3100
                    'interval': card.ivl,
                    'note': card.nid,
                    'type': card.type,
                    'queue': card.queue,
                    'due': card.due,
                    'reps': card.reps,
                    'lapses': card.lapses,
                    'left': card.left,
                    'mod': card.mod,
                    'nextReviews': list(nextReviews),
                    'flags': card.flags,
                })
            except NotFoundError:
                # Anki will give a NotFoundError if the card ID does not exist.
                # Best behavior is probably to add an 'empty card' to the
                # returned result, so that the items of the input and return
                # lists correspond.
                result.append({})

        return result

    @util.api()
    def cardsModTime(self, cards):
        result = []
        for cid in cards:
            try:
                card = self.getCard(cid)
                result.append({
                    'cardId': card.id,
                    'mod': card.mod,
                })
            except NotFoundError:
                # Anki will give a NotFoundError if the card ID does not exist.
                # Best behavior is probably to add an 'empty card' to the
                # returned result, so that the items of the input and return
                # lists correspond.
                result.append({})
        return result

    @util.api()
    def forgetCards(self, cards):
        self.startEditing()
        request = ScheduleCardsAsNew(
            card_ids=cards,
            log=True,
            restore_position=True,
            reset_counts=False,
            context=None,
        )
        self.collection()._backend.schedule_cards_as_new(request)

    @util.api()
    def relearnCards(self, cards):
        self.startEditing()
        scids = anki.utils.ids2str(cards)
        self.collection().db.execute('update cards set type=3, queue=1 where id in ' + scids)


    @util.api()
    def answerCards(self, answers):
        scheduler = self.scheduler()
        success = []
        for answer in answers:
            try:
                cid = answer['cardId']
                ease = answer['ease']
                card = self.getCard(cid)
                card.start_timer()
                scheduler.answerCard(card, ease)
                success.append(True)
            except NotFoundError:
                success.append(False)

        return success


    @util.api()
    def chatReviewCapabilities(self):
        return {
            'protocol': self.CHAT_REVIEW_PROTOCOL,
            'ticketProtocolVersion': self.CHAT_REVIEW_PROTOCOL,
            'supportsTickets': True,
            'supportsIdempotentReplay': True,
            'supportsCancel': True,
            'supportsRecovery': True,
            'supportsStatus': True,
            'supportsAbandon': True,
            'generationHash': self.chatReviewGenerationHash(),
            'ankiVersion': aqt.appVersion,
            'ankiVersionVerified': self.chatReviewVersionVerified(),
            'testedAnkiVersions': list(self.CHAT_REVIEW_TESTED_ANKI_VERSIONS),
            'fsrs': self.chatReviewFsrsStatus(),
        }


    @util.api()
    def chatReviewStatus(self):
        """Return non-secret recovery metadata without exposing bearer state."""
        with self.chatReviewLock:
            self.cleanupChatReviewRegistry()
            if not self.chatReviewPending:
                return {
                    'active': False,
                    'generationHash': self.chatReviewGenerationHash(),
                }

            sessionId, pending = next(iter(self.chatReviewPending.items()))
            ownerHash = hashlib.sha256(sessionId.encode('utf-8')).hexdigest()[:12]
            self.chatReviewStatusObserved[ownerHash] = time.time()
            return {
                'active': True,
                'generationHash': self.chatReviewGenerationHash(),
                'ownerHash': ownerHash,
                'cardId': pending['cardId'],
                'deckName': pending['deckName'],
                'pendingAgeSeconds': max(0, int(time.time() - pending['createdAt'])),
                'expiresAt': pending['createdAt'] + self.CHAT_REVIEW_PENDING_TTL_SECONDS,
            }


    @util.api()
    def chatReviewAbandon(self, generationHash, ownerHash, expectedCardId, confirm=False):
        """Abandon a recently inspected pending card without scheduling it."""
        if confirm is not True:
            raise Exception('confirm must be true')
        self.requireChatReviewVersionVerified()
        with self.chatReviewLock:
            self.cleanupChatReviewRegistry()
            if generationHash != self.chatReviewGenerationHash():
                self.chatReviewError('REVIEW_COLLECTION_CHANGED', 'profile/collection generation changed')
            observedAt = self.chatReviewStatusObserved.get(ownerHash)
            if observedAt is None or time.time() - observedAt > 60:
                self.chatReviewError('REVIEW_STATUS_STALE', 'a recent matching status check is required')
            if not self.chatReviewPending:
                self.chatReviewError('REVIEW_TICKET_UNKNOWN', 'no pending review exists')
            sessionId, pending = next(iter(self.chatReviewPending.items()))
            actualOwnerHash = hashlib.sha256(sessionId.encode('utf-8')).hexdigest()[:12]
            if actualOwnerHash != ownerHash or pending['cardId'] != expectedCardId:
                self.chatReviewError('REVIEW_CARD_MISMATCH', 'active review metadata changed')
            del self.chatReviewPending[sessionId]
            self.chatReviewStatusObserved.pop(ownerHash, None)
            return {'success': True, 'abandoned': True, 'cardId': expectedCardId}


    @util.api()
    def chatReviewNext(self, sessionId, deckName=None, includeLearning=True, includeNew=True):
        if not isinstance(sessionId, str) or not sessionId:
            raise Exception('sessionId must be a non-empty string')
        self.requireChatReviewVersionVerified()

        with self.chatReviewLock:
            self.cleanupChatReviewRegistry()
            if sessionId in self.chatReviewExpired:
                self.chatReviewError('REVIEW_TICKET_EXPIRED', 'pending ticket expired')
            existing = self.chatReviewPending.get(sessionId)
            if existing is not None:
                try:
                    self.validateChatReviewIdentity(existing)
                except Exception:
                    del self.chatReviewPending[sessionId]
                    raise
                return copy.deepcopy(existing['response'])

            if self.chatReviewPending:
                owner = next(iter(self.chatReviewPending.keys()))
                ownerHash = hashlib.sha256(owner.encode('utf-8')).hexdigest()[:12]
                self.chatReviewError(
                    'REVIEW_SESSION_BUSY',
                    'another review session is active (owner sha256:{})'.format(ownerHash),
                )

            return self.chatReviewCreatePending(
                sessionId, deckName, bool(includeLearning), bool(includeNew)
            )


    @util.api()
    def chatReviewAnswer(self, sessionId, ticket, cardId, rating, returnNext=True):
        if not isinstance(sessionId, str) or not sessionId:
            raise Exception('sessionId must be a non-empty string')
        if not isinstance(ticket, str) or not ticket:
            raise Exception('ticket must be a non-empty string')
        if not isinstance(rating, int) or isinstance(rating, bool) or rating < 1 or rating > 4:
            raise Exception('rating must be an integer from 1 through 4')
        self.requireChatReviewVersionVerified()

        with self.chatReviewLock:
            pendingBeforeCleanup = self.chatReviewPending.get(sessionId)
            if (
                pendingBeforeCleanup is not None
                and pendingBeforeCleanup['ticket'] == ticket
                and time.time() - pendingBeforeCleanup['createdAt'] > self.CHAT_REVIEW_PENDING_TTL_SECONDS
            ):
                del self.chatReviewPending[sessionId]
                self.chatReviewExpired[sessionId] = time.time()
                self.chatReviewError('REVIEW_TICKET_EXPIRED', 'pending ticket expired')
            self.cleanupChatReviewRegistry()
            completed = self.chatReviewCompleted.get(ticket)
            if completed is not None:
                self.chatReviewCompleted.move_to_end(ticket)
                if completed['sessionId'] != sessionId or completed['cardId'] != cardId:
                    self.chatReviewError('REVIEW_CARD_MISMATCH', 'completed ticket does not match session/card')
                if completed['rating'] != rating:
                    self.chatReviewError(
                        'REVIEW_TICKET_ALREADY_USED_DIFFERENT_RATING',
                        'ticket was already consumed with a different rating',
                    )
                response = copy.deepcopy(completed['response'])
                response['replayed'] = True
                return response

            pending = self.chatReviewPending.get(sessionId)
            if pending is None:
                self.chatReviewError('REVIEW_TICKET_UNKNOWN', 'ticket is unknown or expired')
            if pending['ticket'] != ticket:
                self.chatReviewError('REVIEW_TICKET_UNKNOWN', 'ticket does not belong to this session')
            if pending['cardId'] != cardId:
                self.chatReviewError('REVIEW_CARD_MISMATCH', 'ticket card does not match cardId')
            try:
                self.validateChatReviewIdentity(pending)
            except Exception:
                del self.chatReviewPending[sessionId]
                raise

            try:
                self.collection().get_card(cardId)
            except NotFoundError:
                del self.chatReviewPending[sessionId]
                self.chatReviewError('REVIEW_CARD_DELETED', 'the pending card no longer exists')

            ratingByEase = {
                1: CardAnswer.AGAIN,
                2: CardAnswer.HARD,
                3: CardAnswer.GOOD,
                4: CardAnswer.EASY,
            }
            scheduler = self.scheduler()
            try:
                # Anki remains the sole scheduling authority. build_answer()
                # selects one of the frozen Anki-generated states, and
                # answer_card() applies every interval/memory-state/revlog
                # mutation atomically inside Anki's scheduler.
                answer = scheduler.build_answer(
                    card=pending['card'],
                    states=pending['states'],
                    rating=ratingByEase[rating],
                )
                scheduler.answer_card(answer)
            except Exception as error:
                self.chatReviewError('REVIEW_QUEUE_STATE_INVALID', str(error))

            del self.chatReviewPending[sessionId]
            nextResult = None
            if returnNext:
                nextResult = self.chatReviewCreatePending(
                    sessionId,
                    pending['deckName'],
                    pending['includeLearning'],
                    pending['includeNew'],
                )

            response = {
                'success': True,
                'replayed': False,
                'ratedCard': {
                    'cardId': cardId,
                    'rating': rating,
                    'ratingDescription': {
                        1: 'Again (incorrect; review again soon)',
                        2: 'Hard (correct with difficulty)',
                        3: 'Good (correct with normal effort)',
                        4: 'Easy (recalled instantly)',
                    }[rating],
                },
                'next': nextResult,
            }
            self.chatReviewCompleted[ticket] = {
                'ticket': ticket,
                'sessionId': sessionId,
                'cardId': cardId,
                'rating': rating,
                'response': copy.deepcopy(response),
                'completedAt': time.time(),
            }
            self.cleanupChatReviewRegistry()
            return response


    @util.api()
    def chatReviewCancel(self, sessionId, ticket):
        with self.chatReviewLock:
            self.cleanupChatReviewRegistry()
            pending = self.chatReviewPending.get(sessionId)
            if pending is None or pending['ticket'] != ticket:
                self.chatReviewError('REVIEW_TICKET_UNKNOWN', 'ticket is unknown or expired')
            del self.chatReviewPending[sessionId]
            return {'success': True, 'cancelled': True}


    @util.api()
    def cardReviews(self, deck, startID):
        return self.database().all(
            'select id, cid, usn, ease, ivl, lastIvl, factor, time, type from revlog ''where id>? and cid in (select id from cards where did=?)',
            startID,
            self.decks().id(deck)
        )


    @util.api()
    def getReviewsOfCards(self, cards):
        COLUMNS = ['cid', 'id', 'usn', 'ease', 'ivl', 'lastIvl', 'factor', 'time', 'type']

        cid_to_reviews = {}
        # 999 is the maximum number of variables sqlite allows
        for cid_batch in util.batched(cards, 999):
            placeholders = ','.join('?' * len(cid_batch))

            cid_reviews = self.collection().db.all('select {} from revlog where cid in ({})'.format(', '.join(COLUMNS), placeholders), *cid_batch)
            for cid_review in cid_reviews:
                cid = cid_review[0]
                reviews = cid_to_reviews.get(cid, [])
                reviews.append(cid_review[1:])
                cid_to_reviews[cid] = reviews

        result = {}
        for card in cards:
            result[card] = [dict(zip(COLUMNS[1:], review)) for review in cid_to_reviews.get(card, [])]

        return result


    @util.api()
    def setDueDate(self, cards, days):
        self.scheduler().set_due_date(cards, days, config_key=None)
        return True


    @util.api()
    def reloadCollection(self):
        self.collection().reset()


    @util.api()
    def getLatestReviewID(self, deck):
        return self.database().scalar(
            'select max(id) from revlog where cid in (select id from cards where did=?)',
            self.decks().id(deck)
        ) or 0


    @util.api()
    def insertReviews(self, reviews):
        if len(reviews) > 0:
            sql = 'insert into revlog(id,cid,usn,ease,ivl,lastIvl,factor,time,type) values '
            for row in reviews:
                sql += '(%s),' % ','.join(map(str, row))
            sql = sql[:-1]
            self.database().execute(sql)


    @util.api()
    def notesInfo(self, notes=None, query=None):
        if notes is None and query is None:
            raise Exception('Must provide either "notes" or a "query"')
        
        if query is not None:
            notes = self.findNotes(query)

        nid_to_card_ids = {}
        # 999 is the maximum number of variables sqlite allows
        for nid_batch in util.batched(notes, 999):
            placeholders = ','.join('?' * len(nid_batch))

            cid_and_nids = self.collection().db.all('select id, nid from cards where nid in ({}) order by ord'.format(placeholders), *nid_batch)
            for cid, nid in cid_and_nids:
                card_ids = nid_to_card_ids.get(nid, [])
                card_ids.append(cid)
                nid_to_card_ids[nid] = card_ids

        result = []
        for nid in notes:
            try:
                note = self.getNote(nid)
                model = note.note_type()

                fields = {}
                for info in model['flds']:
                    order = info['ord']
                    name = info['name']
                    fields[name] = {'value': note.fields[order], 'order': order}

                result.append({
                    'noteId': note.id,
                    'profile': self.window().pm.name,
                    'tags' : note.tags,
                    'fields': fields,
                    'modelName': model['name'],
                    'mod': note.mod,
                    'cards': nid_to_card_ids[nid],
                })
            except NotFoundError:
                # Anki will give a NotFoundError if the note ID does not exist.
                # Best behavior is probably to add an 'empty card' to the
                # returned result, so that the items of the input and return
                # lists correspond.
                result.append({})

        return result

    @util.api()
    def notesModTime(self, notes):
        result = []
        for nid in notes:
            try:
                note = self.getNote(nid)
                result.append({
                    'noteId': note.id,
                    'mod': note.mod
                })
            except NotFoundError:
                # Anki will give a NotFoundError if the note ID does not exist.
                # Best behavior is probably to add an 'empty card' to the
                # returned result, so that the items of the input and return
                # lists correspond.
                result.append({})
        return result

    @util.api()
    def deleteNotes(self, notes):
        self.collection().remove_notes(notes)


    @util.api()
    def removeEmptyNotes(self):
        for model in self.collection().models.all():
            if self.collection().models.use_count(model) == 0:
                self.collection().models.remove(model["id"])
        self.window().requireReset()


    @util.api()
    def cardsToNotes(self, cards):
        return self.collection().db.list('select distinct nid from cards where id in ' + anki.utils.ids2str(cards))


    @util.api()
    def guiBrowse(self, query=None, reorderCards=None):
        browser = aqt.dialogs.open('Browser', self.window())
        browser.activateWindow()

        if query is not None:
            browser.form.searchEdit.lineEdit().setText(query)
            if hasattr(browser, 'onSearch'):
                browser.onSearch()
            else:
                browser.onSearchActivated()

        if reorderCards is not None:
            if not isinstance(reorderCards, dict):
                raise Exception('reorderCards should be a dict: {}'.format(reorderCards))
            if not ('columnId' in reorderCards and 'order' in reorderCards):
                raise Exception('Must provide a "columnId" and a "order" property"')

            cardOrder = reorderCards['order']
            if cardOrder not in ('ascending', 'descending'):
                raise Exception('invalid card order: {}'.format(reorderCards['order']))

            cardOrder = Qt.SortOrder.DescendingOrder if cardOrder == 'descending' else Qt.SortOrder.AscendingOrder
            columnId = browser.table._model.active_column_index(reorderCards['columnId'])
            if columnId == None:
                raise Exception('invalid columnId: {}'.format(reorderCards['columnId']))

            browser.table._on_sort_column_changed(columnId, cardOrder)

        return self.findCards(query)


    @util.api()
    def guiEditNote(self, note):
        Edit.open_dialog_and_show_note_with_id(note)

    @util.api()
    def guiSelectNote(self, note):
        print('guiSelectNote actually selects card IDs and is deprecated; use guiSelectCard')
        return self.guiSelectCard(note)

    @util.api()
    def guiSelectCard(self, card):
        (creator, instance) = aqt.dialogs._dialogs['Browser']
        if instance is None:
            return False
        instance.table.clear_selection()
        instance.table.select_single_card(card)
        return True

    @util.api()
    def guiSelectedNotes(self):
        (creator, instance) = aqt.dialogs._dialogs['Browser']
        if instance is None:
            return []
        return instance.selectedNotes()

    @util.api()
    def guiAddCards(self, note=None):
        if note is not None:
            collection = self.collection()

            deck = collection.decks.by_name(note['deckName'])
            if deck is None:
                raise Exception('deck was not found: {}'.format(note['deckName']))

            collection.decks.select(deck['id'])
            savedMid = deck.pop('mid', None)

            model = collection.models.by_name(note['modelName'])
            if model is None:
                raise Exception('model was not found: {}'.format(note['modelName']))

            collection.models.set_current(model)
            collection.models.update(model)

            ankiNote = anki.notes.Note(collection, model)

            # fill out card beforehand, so we can be sure of the note id
            if 'fields' in note:
                for name, value in note['fields'].items():
                    if name in ankiNote:
                        ankiNote[name] = value

            self.addMediaFromNote(ankiNote, note)

            if 'tags' in note:
                ankiNote.tags = note['tags']

            def openNewWindow():
                nonlocal ankiNote

                addCards = aqt.dialogs.open('AddCards', self.window())

                if savedMid:
                    deck['mid'] = savedMid

                addCards.editor.set_note(ankiNote)

                addCards.activateWindow()

                aqt.dialogs.open('AddCards', self.window())
                addCards.setAndFocusNote(addCards.editor.note)

            currentWindow = aqt.dialogs._dialogs['AddCards'][1]

            if currentWindow is not None:
                currentWindow.closeWithCallback(openNewWindow)
            else:
                openNewWindow()

            return ankiNote.id

        else:
            addCards = aqt.dialogs.open('AddCards', self.window())
            addCards.activateWindow()

            return addCards.editor.note.id


    @util.api()
    def guiReviewActive(self):
        return self.reviewer().card is not None and self.window().state == 'review'


    @util.api()
    def guiCurrentCard(self):
        if not self.guiReviewActive():
            raise Exception('Gui review is not currently active.')

        reviewer = self.reviewer()
        card = reviewer.card
        model = card.note_type()
        note = card.note()

        fields = {}
        for info in model['flds']:
            order = info['ord']
            name = info['name']
            fields[name] = {'value': note.fields[order], 'order': order}

        buttonList = reviewer._answerButtonList()
        return {
            'cardId': card.id,
            'fields': fields,
            'fieldOrder': card.ord,
            'question': util.cardQuestion(card),
            'answer': util.cardAnswer(card),
            'buttons': [b[0] for b in buttonList],
            'nextReviews': [reviewer.mw.col.sched.nextIvlStr(reviewer.card, b[0], True) for b in buttonList],
            'modelName': model['name'],
            'deckName': self.deckNameFromId(card.did),
            'css': model['css'],
            'template': card.template()['name']
        }


    @util.api()
    def guiStartCardTimer(self):
        if not self.guiReviewActive():
            return False

        card = self.reviewer().card
        if card is not None:
            card.startTimer()
            return True

        return False


    @util.api()
    def guiShowQuestion(self):
        if self.guiReviewActive():
            self.reviewer()._showQuestion()
            return True

        return False


    @util.api()
    def guiShowAnswer(self):
        if self.guiReviewActive():
            self.window().reviewer._showAnswer()
            return True

        return False


    @util.api()
    def guiAnswerCard(self, ease):
        if not self.guiReviewActive():
            return False

        reviewer = self.reviewer()
        if reviewer.state != 'answer':
            return False
        if ease <= 0 or ease > self.scheduler().answerButtons(reviewer.card):
            return False

        reviewer._answerCard(ease)
        return True

    @util.api()
    def guiPlayAudio(self):
        if not self.guiReviewActive():
            return False

        reviewer = self.reviewer()

        reviewer.replayAudio()

        return True

    @util.api()
    def guiUndo(self):
        self.window().undo()
        return True


    @util.api()
    def guiDeckOverview(self, name):
        collection = self.collection()
        if collection is not None:
            deck = collection.decks.by_name(name)
            if deck is not None:
                collection.decks.select(deck['id'])
                self.window().onOverview()
                return True

        return False


    @util.api()
    def guiDeckBrowser(self):
        self.window().moveToState('deckBrowser')


    @util.api()
    def guiDeckReview(self, name):
        if self.guiDeckOverview(name):
            self.window().moveToState('review')
            return True

        return False


    @util.api()
    def guiImportFile(self, path=None):
        """
        Open Import File (Ctrl+Shift+I) dialog with provided file path.
        If no path is given, the user will be prompted to select a file.
        Only supported from Anki version >=2.1.52

        path: string
            import file path, note on Windows you must use forward slashes.
        """
        if anki_version >= (2, 1, 52):
            from aqt.import_export.importing import import_file, prompt_for_file_then_import
        else:
            raise Exception('guiImportFile is only supported from Anki version >=2.1.52')

        if hasattr(Qt, 'WindowStaysOnTopHint'):
            # Qt5
            WindowOnTopFlag = Qt.WindowStaysOnTopHint
        elif hasattr(Qt, 'WindowType') and hasattr(Qt.WindowType, 'WindowStaysOnTopHint'):
            # Qt6
            WindowOnTopFlag = Qt.WindowType.WindowStaysOnTopHint
        else:
            # Unsupported, don't try to bring window to top
            WindowOnTopFlag = None

        # Bring window to top for user to review import settings.
        if WindowOnTopFlag is not None:
            try:
                # [Step 1/2] set always on top flag, show window (it stays on top for now)
                self.window().setWindowFlags(self.window().windowFlags() | WindowOnTopFlag)  
                self.window().show()
            finally:
                # [Step 2/2] clear always on top flag, show window (it doesn't stay on top anymore)
                self.window().setWindowFlags(self.window().windowFlags() & ~WindowOnTopFlag) 
                self.window().show()

        if path is None:
            prompt_for_file_then_import(self.window())
        else:
            import_file(self.window(), path)


    @util.api()
    def guiExitAnki(self):
        timer = QTimer()
        timer.timeout.connect(self.window().close)
        timer.start(1000) # 1s should be enough to allow the response to be sent.


    @util.api()
    def guiCheckDatabase(self):
        self.window().onCheckDB()
        return True


    @util.api()
    def addNotes(self, notes):
        results = []
        errs = []

        for note in notes:
            try:
                results.append(self.addNote(note))
            except Exception as e:
                # I specifically chose to continue, so we gather all the errors of all notes (ie not break)
                errs.append(str(e))

        if errs:
            # Roll back the changes so on error nothing happens
            self.deleteNotes(results)
            raise Exception(str(errs))

        return results


    @util.api()
    def canAddNotes(self, notes):
        results = []
        for note in notes:
            results.append(self.canAddNote(note))

        return results

    @util.api()
    def canAddNotesWithErrorDetail(self, notes):
        results = []
        for note in notes:
            results.append(self.canAddNoteWithErrorDetail(note))

        return results


    @util.api()
    def exportPackage(self, deck, path, includeSched=False):
        collection = self.collection()
        if collection is not None:
            deck = collection.decks.by_name(deck)
            if deck is not None:
                exporter = AnkiPackageExporter(collection)
                exporter.did = deck['id']
                exporter.includeSched = includeSched
                exporter.exportInto(path)
                return True

        return False


    @util.api()
    def importPackage(self, path):
        collection = self.collection()
        if collection is not None:
            try:
                self.startEditing()
                importer = AnkiPackageImporter(collection, path)
                importer.run()
            except:
                raise
            else:
                return True

        return False


    @util.api()
    def apiReflect(self, scopes=None, actions=None):
        if not isinstance(scopes, list):
            raise Exception('scopes has invalid value')
        if not (actions is None or isinstance(actions, list)):
            raise Exception('actions has invalid value')

        cls = type(self)
        scopes2 = []
        result = {'scopes': scopes2}

        if 'actions' in scopes:
            if actions is None:
                actions = dir(cls)

            methodNames = []
            for methodName in actions:
                if not isinstance(methodName, str):
                    pass
                method = getattr(cls, methodName, None)
                if method is not None and getattr(method, 'api', False):
                    methodNames.append(methodName)

            scopes2.append('actions')
            result['actions'] = methodNames

        return result


#
# Entry
#

# when run inside Anki, `__name__` would be either numeric,
# or, if installed via `link.sh`, `AnkiConnectDev`
if __name__ != "plugin":
    if platform.system() == "Windows" and anki_version == (2, 1, 50):
        util.patch_anki_2_1_50_having_null_stdout_on_windows()

    Edit.register_with_anki()

    ac = AnkiConnect()
    ac.initLogging()
    ac.startWebServer()
