"""Centralized UI text — German is the default/only language rendered for
now, but every string lives here (not scattered in templates) so English can
be added later without hunting through HTML. No translation framework; this
is intentionally a plain dict (see docs/mvp/kitchen-handover.md §29 of the
original prompt: "do not add a complicated translation service").
"""

DE = {
    "app_name": "Küchenübergabe",
    "home_title": "Heutige Küche",
    "items_to_prepare": "Artikel vorzubereiten",
    "overdue_heading": "ÜBERFÄLLIG",
    "today_heading": "HEUTE VORBEREITEN",
    "no_active_tasks": "Alles erledigt.",
    "sections_heading": "BEREICHE",
    "products_heading": "PRODUKTE",
    "done_button": "FERTIG",
    "prepare_tomorrow_button": "FÜR MORGEN VORBEREITEN",
    "prepared_tomorrow_message": "Für morgen vorgemerkt.",
    "already_marked_message": "Bereits für morgen vorgemerkt.",
    "completed_message": "Erledigt.",
    "already_completed_message": "War bereits erledigt.",
    "choose_worker_title": "Wer bist du?",
    "choose_worker_prompt": "Wähle deinen Namen oder gib einen neuen ein.",
    "new_worker_placeholder": "Neuer Name",
    "continue_button": "Weiter",
    "change_worker": "Name ändern",
    "due_yesterday_or_earlier": "Fällig: vor heute",
    "due_today": "Fällig: heute",
}

# Texts dict injected into every Jinja template as `t`. Swap this for a
# language-aware lookup (e.g. by an Accept-Language header or a user
# preference) when English support is actually needed — the templates
# already only ever reference `t.<key>`, never literal German strings.
TEXTS = DE
