export class ObliqError extends Error {
  public readonly code: string;
  public readonly statusCode: number;
  public readonly retryable: boolean;
  public readonly details?: Record<string, unknown>;

  constructor(
    code: string,
    message: string,
    statusCode: number = 400,
    retryable: boolean = false,
    details?: Record<string, unknown>
  ) {
    super(message);
    this.name = "ObliqError";
    this.code = code;
    this.statusCode = statusCode;
    this.retryable = retryable;
    this.details = details;
    Object.setPrototypeOf(this, new.target.prototype);
  }
}

export class AuthenticationError extends ObliqError {
  constructor(message: string = "Invalid or missing credentials", details?: Record<string, unknown>) {
    super("authentication_error", message, 401, false, details);
    this.name = "AuthenticationError";
  }
}

export class ForbiddenError extends ObliqError {
  constructor(message: string = "Insufficient permissions or scopes", details?: Record<string, unknown>) {
    super("authorization_error", message, 403, false, details);
    this.name = "ForbiddenError";
  }
}

export class NotFoundError extends ObliqError {
  constructor(message: string = "Requested resource not found", details?: Record<string, unknown>) {
    super("not_found", message, 404, false, details);
    this.name = "NotFoundError";
  }
}

export class RateLimitError extends ObliqError {
  public readonly retryAfterSeconds: number;

  constructor(retryAfterSeconds: number = 60, details?: Record<string, unknown>) {
    super("rate_limit_exceeded", `Rate limit exceeded. Retry after ${retryAfterSeconds}s`, 429, true, details);
    this.name = "RateLimitError";
    this.retryAfterSeconds = retryAfterSeconds;
  }
}

export class PayloadTooLargeError extends ObliqError {
  constructor(message: string = "Document exceeds allowable size limit", details?: Record<string, unknown>) {
    super("payload_too_large", message, 413, false, details);
    this.name = "PayloadTooLargeError";
  }
}

export class ValidationError extends ObliqError {
  constructor(message: string = "Request validation failed", details?: Record<string, unknown>) {
    super("validation_error", message, 422, false, details);
    this.name = "ValidationError";
  }
}

export class ServerError extends ObliqError {
  constructor(message: string = "Internal server error occurred", statusCode: number = 500, details?: Record<string, unknown>) {
    super("server_error", message, statusCode, true, details);
    this.name = "ServerError";
  }
}

export class NetworkError extends ObliqError {
  constructor(message: string = "Network request failed to reach Obliq API") {
    super("network_error", message, 0, true);
    this.name = "NetworkError";
  }
}
