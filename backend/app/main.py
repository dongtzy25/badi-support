from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.routers import misc, tickets, ws

app = FastAPI(title="Badi eSIM Support API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # the React dev server
    allow_methods=["*"],
    allow_headers=["*"],
)


def friendly_message(err: dict) -> str:
    """Pydantic's default messages are written for developers; reword the common ones."""
    ctx = err.get("ctx") or {}
    field = str(err["loc"][-1]) if err.get("loc") else ""
    match err["type"]:
        case "missing":
            return "This field is required"
        case "string_too_short":
            return "This field is required" if ctx.get("min_length") == 1 else f"Must be at least {ctx['min_length']} characters"
        case "string_too_long":
            return f"Must be at most {ctx['max_length']} characters"
        case "string_pattern_mismatch" if field == "order_id":
            return "Order ID can only contain letters, numbers and dashes (e.g. ORD-10293)"
        case "value_error" if field == "customer_email" or "email" in err["msg"]:
            return "Enter a valid email address"
        case "extra_forbidden":
            return f"Unknown field '{field}'"
    return err["msg"].removeprefix("Value error, ")


@app.exception_handler(RequestValidationError)
def validation_error_handler(request: Request, exc: RequestValidationError):
    """Turn FastAPI's detailed validation output into a short, readable list:
    {"detail": "Validation failed", "errors": [{"field": "subject", "message": "..."}]}"""
    errors = []
    for err in exc.errors():
        # loc looks like ("body", "subject") or ("query", "limit"); drop the leading "body".
        loc = [str(p) for p in err["loc"]]
        if loc and loc[0] == "body":
            loc = loc[1:]
        errors.append({"field": ".".join(loc) or None, "message": friendly_message(err)})
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={"detail": "Validation failed", "errors": errors},
    )


app.include_router(tickets.router)
app.include_router(misc.router)
app.include_router(ws.router)


@app.get("/health", tags=["health"])
def health():
    return {"status": "ok"}
