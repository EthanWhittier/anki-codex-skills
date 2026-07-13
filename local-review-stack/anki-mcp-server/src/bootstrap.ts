import { Logger, LoggerService } from "@nestjs/common";
import { appendFileSync } from "fs";
import { resolve } from "path";
import { pino } from "pino";

const timingLogPath =
  process.env.ANKI_MCP_TIMING_LOG || resolve(__dirname, "..", "anki-mcp-timing.log");

function writeTimingLog(level: string, message: any, context?: string) {
  if (typeof message !== "string" || !message.includes("[timing")) {
    return;
  }

  const contextPart = context ? ` ${context}` : "";
  try {
    appendFileSync(
      timingLogPath,
      `${new Date().toISOString()} pid=${process.pid} ${level}${contextPart} ${message}\n`,
      "utf8",
    );
  } catch {
    // Timing logs are diagnostic only; never affect MCP behavior.
  }
}

function patchNestLoggerForTimingLogs() {
  const proto = Logger.prototype as Logger & { __timingLogPatched?: boolean };
  if (proto.__timingLogPatched) {
    return;
  }
  proto.__timingLogPatched = true;

  const originalLog = proto.log;
  proto.log = function patchedLog(message: any, context?: string) {
    writeTimingLog("info", message, context);
    return originalLog.call(this, message, context);
  };

  const originalWarn = proto.warn;
  proto.warn = function patchedWarn(message: any, context?: string) {
    writeTimingLog("warn", message, context);
    return originalWarn.call(this, message, context);
  };

  const originalError = proto.error;
  proto.error = function patchedError(
    message: any,
    stack?: string,
    context?: string,
  ) {
    writeTimingLog("error", message, context);
    return originalError.call(this, message, stack, context);
  };

  const originalDebug = proto.debug;
  proto.debug = function patchedDebug(message: any, context?: string) {
    writeTimingLog("debug", message, context);
    return originalDebug.call(this, message, context);
  };

  const originalVerbose = proto.verbose;
  proto.verbose = function patchedVerbose(message: any, context?: string) {
    writeTimingLog("verbose", message, context);
    return originalVerbose.call(this, message, context);
  };
}

patchNestLoggerForTimingLogs();

/**
 * Creates a Pino logger configured for the specified transport mode
 *
 * @param destination - File descriptor: 1 (stdout) for HTTP, 2 (stderr) for STDIO
 * @returns Configured pino logger instance
 */
export function createPinoLogger(destination: 1 | 2) {
  return pino({
    level: process.env.LOG_LEVEL || "info",
    transport: {
      target: "pino-pretty",
      options: {
        destination,
        colorize: true,
        translateTime: "HH:MM:ss Z",
        ignore: "pid,hostname",
      },
    },
  });
}

/**
 * Creates a NestJS-compatible logger service from a Pino logger
 *
 * @param pinoLogger - The pino logger instance
 * @returns NestJS LoggerService implementation
 */
export function createLoggerService(pinoLogger: any): LoggerService {
  return {
    log: (message: any, context?: string) => {
      pinoLogger.info({ context }, message);
      writeTimingLog("info", message, context);
    },
    error: (message: any, trace?: string, context?: string) => {
      pinoLogger.error({ context, trace }, message);
      writeTimingLog("error", message, context);
    },
    warn: (message: any, context?: string) => {
      pinoLogger.warn({ context }, message);
      writeTimingLog("warn", message, context);
    },
    debug: (message: any, context?: string) => {
      pinoLogger.debug({ context }, message);
      writeTimingLog("debug", message, context);
    },
    verbose: (message: any, context?: string) => {
      pinoLogger.trace({ context }, message);
      writeTimingLog("verbose", message, context);
    },
  };
}
