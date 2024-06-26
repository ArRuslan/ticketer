from ticketer.exceptions import ErrorMessageException


class Errors:
    WRONG_CREDENTIALS = ErrorMessageException(400, 1, "Wrong email or password!")
    WRONG_CAPTCHA = ErrorMessageException(400, 2, "Failed to verify captcha!")
    WRONG_MFA_CODE = ErrorMessageException(400, 3, "Invalid two-factor authentication code.")
    WRONG_PASSWORD = ErrorMessageException(400, 4, "Wrong password.")
    WRONG_MFA_KEY = ErrorMessageException(400, 5, "Invalid two-factor authentication key.")

    UNKNOWN_EVENT = ErrorMessageException(404, 6, "Unknown event.")
    UNKNOWN_TICKET = ErrorMessageException(404, 7, "Unknown ticket.")
    UNKNOWN_PLAN = ErrorMessageException(404, 8, "Unknown event plan.")
    UNKNOWN_USER = ErrorMessageException(404, 9, "Unknown user.")
    UNKNOWN_LOCATION = ErrorMessageException(404, 10, "Unknown location.")

    INVALID_CARD_DETAILS = ErrorMessageException(400, 11, "Card details you provided are invalid.")
    INVALID_TICKET = ErrorMessageException(400, 12, "Invalid ticket.")
    INVALID_TOKEN = ErrorMessageException(401, 13, "Invalid token.")
    INVALID_AMOUNT = ErrorMessageException(400, 14, "Invalid amount.")
    INVALID_MAX_TICKETS = ErrorMessageException(400, 15, "Invalid max_tickets.")
    INVALID_IMAGE = ErrorMessageException(400, 16, "Invalid image provided.")

    USER_EXISTS = ErrorMessageException(400, 17, "User with this email already exists!")
    USER_BANNED = ErrorMessageException(403, 18, "Your account is banned!")
    PHONE_NUMBER_USED = ErrorMessageException(400, 19, "This phone number is already used.")
    NEED_PASSWORD = ErrorMessageException(400, 20, "You need to enter your password.")
    MFA_ALREADY_ENABLED = ErrorMessageException(400, 21, "Two-factory authentication is already enabled.")
    MFA_ALREADY_DISABLED = ErrorMessageException(400, 22, "Two-factory authentication is already disabled.")
    GOOGLE_ALREADY_CONNECTED = ErrorMessageException(400, 23, "You already have connected google account.")
    GOOGLE_ALREADY_CONNECTED_TO_OTHER = ErrorMessageException(400, 24, "This account is already connected.")
    TICKET_ALREADY_VERIFIED = ErrorMessageException(400, 25, "Already verified.")
    TICKETS_NOT_AVAILABLE = ErrorMessageException(400, 26, "{} tickets not available. Try lowering tickets amount.")
    TICKET_CANNOT_CANCEL = ErrorMessageException(400, 27, "This ticket cannot be cancelled.")
    PAYMENT_NOT_RECEIVED = ErrorMessageException(400, 28, "Payment not received yet.")
    PAYMENT_NOT_RECEIVED_TOKEN = ErrorMessageException(403, 29, "Payment is not received for this ticket.")
    CANNOT_BAN = ErrorMessageException(403, 30, "You cannot ban this user.")
    CANNOT_UNBAN = ErrorMessageException(403, 31, "You cannot unban this user.")
    TICKET_ANOTHER_EVENT = ErrorMessageException(400, 32, "Ticket is issued for another event.")
    INSUFFICIENT_PERMISSIONS = ErrorMessageException(403, 33, "Insufficient permissions.")

    INVALID_ROLE = ErrorMessageException(400, 34, "Invalid role.")
