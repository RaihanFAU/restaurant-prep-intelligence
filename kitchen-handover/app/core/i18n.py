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
    "due_yesterday_or_earlier": "Fällig: vor heute",
    "due_today": "Fällig: heute",

    # --- auth ---
    "email_label": "E-Mail",
    "password_label": "Passwort",
    "login_button": "Anmelden",
    "logout_button": "ABMELDEN",
    "logged_in_as": "Angemeldet als",
    "login_error": "E-Mail oder Passwort ist falsch.",
    "csrf_error": "Sitzung abgelaufen, bitte erneut versuchen.",
    "admin_link": "ADMIN",

    # --- admin: shared ---
    "admin_dashboard_title": "Admin",
    "admin_products_card": "PRODUKTE",
    "admin_stations_card": "STATIONEN",
    "admin_sections_card": "BEREICHE",
    "admin_users_card": "BENUTZER",
    "admin_tasks_card": "AUFGABEN",
    "active_label": "Aktiv",
    "inactive_label": "Inaktiv",
    "edit_button": "BEARBEITEN",
    "deactivate_button": "DEAKTIVIEREN",
    "activate_button": "AKTIVIEREN",
    "save_button": "SPEICHERN",
    "add_button": "HINZUFÜGEN",
    "back_link": "Zurück",

    # --- admin: products ---
    "product_name_de_label": "Name (DE)",
    "product_name_en_label": "Name (EN, optional)",
    "station_label": "Station",
    "section_label": "Bereich (optional)",
    "no_section_option": "— kein Bereich —",
    "search_placeholder": "Suchen...",

    # --- admin: stations/sections ---
    "station_name_label": "Name der Station",
    "section_name_label": "Name des Bereichs",

    # --- admin: users ---
    "display_name_label": "Anzeigename",
    "role_label": "Rolle",
    "initial_password_label": "Passwort",
    "new_password_label": "Neues Passwort",
    "reset_password_button": "PASSWORT ÄNDERN",

    # --- admin: tasks / priority ---
    "priority_label": "Priorität",
    "pin_button": "ANHEFTEN",
    "unpin_button": "LÖSEN",
    "pinned_label": "ANGEHEFTET",
    "due_date_label": "Fällig am",
    "created_by_label": "Erstellt von",
    "completed_by_label": "Erledigt von",
    "create_task_button": "AUFGABE ERSTELLEN",
}

# Texts dict injected into every Jinja template as `t`. Swap this for a
# language-aware lookup (e.g. by an Accept-Language header or a user
# preference) when English support is actually needed — the templates
# already only ever reference `t.<key>`, never literal German strings.
TEXTS = DE
