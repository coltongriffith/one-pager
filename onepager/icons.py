"""Small built-in icon set rendered as inline SVG (stroke = currentColor)."""

_WRAP = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" '
    'stroke-linecap="round" stroke-linejoin="round" xmlns="http://www.w3.org/2000/svg">{}</svg>'
)

_PATHS = {
    "growth": '<path d="M3 17l5-5 4 4 8-8"/><path d="M14 8h6v6"/><path d="M3 21h18"/>',
    "network": '<circle cx="12" cy="5" r="2.2"/><circle cx="5" cy="18" r="2.2"/>'
    '<circle cx="19" cy="18" r="2.2"/><path d="M10.8 6.8L6.2 16M13.2 6.8l4.6 9.2M7.2 18h9.6"/>',
    "education": '<path d="M12 4L2 9l10 5 10-5-10-5z"/><path d="M6 11.5V16c0 1.5 2.7 3 6 3s6-1.5 6-3v-4.5"/>',
    "leaf": '<path d="M5 19C5 9 11 4 20 4c0 9-5 15-15 15z"/><path d="M5 19c2-5 6-9 11-11"/>',
    "shield": '<path d="M12 3l8 3v6c0 4.5-3.2 7.8-8 9-4.8-1.2-8-4.5-8-9V6l8-3z"/><path d="M9 12l2 2 4-4"/>',
    "flask": '<path d="M10 3h4M10 3v6l-5.5 9A2 2 0 0 0 6.2 21h11.6a2 2 0 0 0 1.7-3L14 9V3"/><path d="M7.5 15h9"/>',
    "globe": '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c2.5 2.5 3.8 5.6 3.8 9S14.5 18.5 12 21c-2.5-2.5-3.8-5.6-3.8-9S9.5 5.5 12 3z"/>',
    "users": '<circle cx="9" cy="8" r="3.2"/><path d="M3 20c0-3.3 2.7-6 6-6s6 2.7 6 6"/>'
    '<path d="M16 5.5a3.2 3.2 0 0 1 0 5"/><path d="M17.5 14.5c2.1.8 3.5 2.9 3.5 5.5"/>',
    "dollar": '<circle cx="12" cy="12" r="9"/><path d="M12 6.5v11M15 8.8c-.6-1-1.7-1.5-3-1.5-1.7 0-3 .9-3 2.3 0 2.9 6 1.7 6 4.7 0 1.4-1.3 2.3-3 2.3-1.4 0-2.6-.6-3.2-1.7"/>',
    "target": '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1.2" fill="currentColor"/>',
    "battery": '<rect x="2" y="8" width="17" height="9" rx="2"/><path d="M22 11v3"/><path d="M6 11v3M9.5 11v3M13 11v3"/>',
    "gear": '<circle cx="12" cy="12" r="3"/><path d="M12 2.5l1.2 2.8 3-.6 1 2.9 2.9 1-.6 3 2.3 2-2.3 2 .6 3-2.9 1-1 2.9-3-.6-1.2 2.6-1.2-2.6-3 .6-1-2.9-2.9-1 .6-3-2.3-2 2.3-2-.6-3 2.9-1 1-2.9 3 .6L12 2.5z"/>',
    "map": '<path d="M9 4L3 6v14l6-2 6 2 6-2V4l-6 2-6-2z"/><path d="M9 4v14M15 6v14"/>',
    "drill": '<path d="M4 21h16"/><path d="M12 21V8"/><path d="M7 8h10l-2-5H9L7 8z"/><path d="M9.5 12h5M10.5 16h3"/>',
    "star": '<path d="M12 3l2.7 5.6 6.1.9-4.4 4.3 1 6.1-5.4-2.9-5.4 2.9 1-6.1L3.2 9.5l6.1-.9L12 3z"/>',
    "handshake": '<path d="M2 7l4-2 5 2 5-2 6 3v7l-5 5-5-4-4 2-4-3"/><path d="M11 7l-4 4 2 2 4-3"/>',
    "building": '<rect x="4" y="3" width="12" height="18"/><path d="M16 9h4v12H4"/><path d="M8 7h2M8 11h2M8 15h2M12 7h1M12 11h1M12 15h1"/>',
    "bolt": '<path d="M13 2L4 14h6l-1 8 9-12h-6l1-8z"/>',
}


def icon_svg(name: str) -> str:
    return _WRAP.format(_PATHS.get(name, _PATHS["star"]))


def available_icons() -> list[str]:
    return sorted(_PATHS)
