"""A comment wall moderated with the ToxicFilter Python SDK, in Flask."""

import os
import re
from pathlib import Path

from flask import Flask, redirect, render_template, request
from toxicfilter import Client, ToxicFilterError, webhooks

from store import Comments

app = Flask(__name__)
comments = Comments(Path(__file__).parent / "data" / "comments.json")
tf = Client(os.environ["TOXICFILTER_KEY"])


@app.get("/")
def wall():
    """The comments, and the form."""
    return render_template("wall.html", comments=comments.published(), held="held" in request.args)


@app.post("/comments")
def post_comment():
    """Moderate a new comment, then publish it, hold it or refuse it."""
    name = request.form.get("name", "").strip()
    body = request.form.get("body", "").strip()

    if not name or not body:
        return show_form(name, body, "Write your name and a comment.")

    id = comments.next_id()

    try:
        verdict = tf.text(
            body,
            surface="comment",
            reference=f"comment_{id}",  # how the webhook finds this comment later
        )
    except ToxicFilterError:
        # Nobody could judge it: hold it rather than publish it unread.
        comments.add(id, name, body, "held", None)
        return redirect("/?held=1", code=303)

    if verdict.blocked:
        return show_form(name, body, verdict.reason or "This comment cannot be published.")

    comments.add(id, name, body, "held" if verdict.needs_review else "published", verdict.id)

    return redirect("/?held=1" if verdict.needs_review else "/", code=303)


@app.post("/webhooks/toxicfilter")
def toxicfilter_webhook():
    """A person decided on a held comment in ToxicFilter: publish it or drop it."""
    event = webhooks.event(
        request.get_data(),  # the RAW body, before any parsing
        request.headers.get("X-ToxicFilter-Signature", ""),
        os.environ.get("TOXICFILTER_WEBHOOK_SECRET", ""),
    )

    if event is None:
        return "", 400

    match = re.fullmatch(r"comment_(\d+)", event["data"].get("reference") or "")

    if event["event"] == "moderation.resolved" and match:
        if event["data"]["action"] == "approved":
            comments.publish(int(match[1]))
        else:
            comments.remove(int(match[1]))

    return "", 204


def show_form(name: str, body: str, error: str):
    """The wall again, with what was typed and why it was not posted."""
    return render_template("wall.html", comments=comments.published(), name=name, body=body, error=error), 422
