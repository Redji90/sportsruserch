from __future__ import annotations

from datetime import date
from urllib.parse import urlencode

from flask import Flask, flash, redirect, render_template, request, url_for

from sports_client import SportsClient, format_tag_meta

app = Flask(__name__)
app.secret_key = "sports-archive-local-dev"

CONTENT_TYPES = [
    ("news", "Новости"),
    ("article", "Материалы"),
    ("blog", "Блоги"),
]

EXAMPLES = [
    {
        "label": "Этери Тутберидзе · 2015",
        "tag": "Этери Тутберидзе",
        "year": 2015,
        "types": ["news"],
    },
    {
        "label": "Алина Загитова · 2018",
        "tag": "Алина Загитова",
        "year": 2018,
        "types": ["news"],
    },
]


def _parse_date(value: str | None, fallback: date) -> date:
    if not value:
        return fallback
    try:
        return date.fromisoformat(value)
    except ValueError:
        return fallback


@app.get("/")
def index():
    today = date.today()
    year = request.args.get("year", type=int)
    if year:
        date_from = date(year, 1, 1)
        date_to = date(year, 12, 31)
    else:
        date_from = _parse_date(request.args.get("date_from"), date(today.year, 1, 1))
        date_to = _parse_date(request.args.get("date_to"), today)

    selected_types = request.args.getlist("types") or ["news"]
    tag_query = (request.args.get("tag") or "").strip()
    results = None
    tag = None
    alternatives = []
    error = None

    if request.args.get("run") and tag_query:
        client = SportsClient()
        try:
            tag, alternatives = client.resolve_tag_with_alts(tag_query)
            results = client.fetch_news(
                tag_id=tag.tag_id,
                date_from=date_from,
                date_to=date_to,
                content_types=selected_types,
                lenta_kind=tag.lenta_kind,
            )
        except Exception as exc:  # noqa: BLE001 — показываем пользователю понятную ошибку
            error = str(exc)

    return render_template(
        "index.html",
        content_types=CONTENT_TYPES,
        examples=EXAMPLES,
        tag_query=tag_query,
        date_from=date_from.isoformat(),
        date_to=date_to.isoformat(),
        selected_types=selected_types,
        year=year,
        tag=tag,
        alternatives=alternatives,
        format_tag_meta=format_tag_meta,
        results=results,
        error=error,
        years=list(range(today.year, 2005, -1)),
    )


@app.post("/search")
def search():
    tag_query = (request.form.get("tag") or "").strip()
    date_from = request.form.get("date_from") or ""
    date_to = request.form.get("date_to") or ""
    types = request.form.getlist("types") or ["news"]
    year = (request.form.get("year") or "").strip()

    if not tag_query:
        flash("Введите название тега")
        return redirect(url_for("index"))

    params: list[tuple[str, str]] = [
        ("tag", tag_query),
        ("run", "1"),
    ]
    if year:
        params.append(("year", year))
    else:
        params.append(("date_from", date_from))
        params.append(("date_to", date_to))
    for t in types:
        params.append(("types", t))

    return redirect("/?" + urlencode(params))


if __name__ == "__main__":
    app.run(debug=True, port=5000)
