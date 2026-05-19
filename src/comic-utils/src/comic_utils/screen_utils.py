"""Primary-monitor positioning helpers backed by ``screeninfo``.

Both helpers lazy-import ``screeninfo`` and fall back gracefully when no monitor
can be enumerated (headless CI, broken Xorg/Wayland session, etc.), so callers
can always use the returned coordinates without further guards.
"""


def get_primary_monitor_offset() -> tuple[int, int]:
    """Return the ``(x, y)`` origin of the primary monitor.

    Falls back to ``(0, 0)`` (the virtual-desktop origin) when ``screeninfo``
    can't import, raises, or reports no primary monitor — so the caller can
    safely add per-app ``--win-left``/``--win-top`` offsets without further
    error handling.
    """
    import screeninfo  # noqa: PLC0415

    # noinspection PyBroadException
    try:
        monitors = screeninfo.get_monitors()
    except Exception:  # noqa: BLE001
        return 0, 0

    for monitor in monitors:
        if monitor.is_primary:
            return monitor.x, monitor.y
    if monitors:
        return monitors[0].x, monitors[0].y
    return 0, 0


def get_centred_position_on_primary_monitor(win_width: int, win_height: int) -> tuple[int, int]:
    """Return the ``(x, y)`` position that centres a ``win_width`` x ``win_height`` window.

    Falls back to ``(100, 100)`` when ``screeninfo`` can't import, raises, or
    reports no monitors.
    """
    import screeninfo  # noqa: PLC0415

    # noinspection PyBroadException
    try:
        monitors = screeninfo.get_monitors()
        primary = next((m for m in monitors if m.is_primary), monitors[0] if monitors else None)
        if primary:
            return (
                primary.x + (primary.width - win_width) // 2,
                primary.y + (primary.height - win_height) // 2,
            )
    except Exception:  # noqa: BLE001, S110
        pass

    return 100, 100
