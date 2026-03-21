"""
A2UI Device Context Detection
Detects device type and context from HTTP request headers
"""

from user_agents import parse as parse_user_agent

from .schemas import DeviceContext, Platform


def detect_device_context(
    user_agent: str | None = None,
    device_type_header: str | None = None,
) -> DeviceContext:
    """
    Detect device context from request headers.

    Args:
        user_agent: User-Agent header string
        device_type_header: Optional X-Device-Type header override

    Returns:
        DeviceContext with device information
    """
    # Default context
    is_mobile = False
    is_tablet = False
    platform: Platform | None = None
    browser: str | None = None

    # Check for explicit device type header first
    if device_type_header:
        device_type_lower = device_type_header.lower()
        if device_type_lower == "mobile":
            is_mobile = True
        elif device_type_lower == "tablet":
            is_tablet = True
        # Desktop is the default (neither mobile nor tablet)

    # Parse User-Agent if available
    if user_agent:
        parsed = parse_user_agent(user_agent)

        # Device type detection (if not overridden by header)
        if not device_type_header:
            is_mobile = parsed.is_mobile
            is_tablet = parsed.is_tablet

        # Platform detection
        os_family = parsed.os.family.lower() if parsed.os.family else ""
        if "ios" in os_family or "iphone" in os_family or "ipad" in os_family:
            platform = Platform.IOS
        elif "android" in os_family:
            platform = Platform.ANDROID
        elif "windows" in os_family:
            platform = Platform.WINDOWS
        elif "mac" in os_family or "macos" in os_family:
            platform = Platform.MACOS
        elif "linux" in os_family:
            platform = Platform.LINUX

        # Browser detection
        browser_family = parsed.browser.family.lower() if parsed.browser.family else ""
        if "chrome" in browser_family:
            browser = "chrome"
        elif "firefox" in browser_family:
            browser = "firefox"
        elif "safari" in browser_family:
            browser = "safari"
        elif "edge" in browser_family:
            browser = "edge"
        elif "samsung" in browser_family:
            browser = "samsung"
        elif "opera" in browser_family:
            browser = "opera"
        else:
            browser = browser_family if browser_family else None

    return DeviceContext(
        isMobile=is_mobile,
        isTablet=is_tablet,
        platform=platform,
        browser=browser,
    )


def get_device_context_from_request(
    user_agent: str | None = None,
    x_device_type: str | None = None,
) -> DeviceContext:
    """
    FastAPI-friendly wrapper for device context detection.

    Usage in router:
        @router.get("/ui")
        async def get_ui(
            request: Request,
            user_agent: str | None = Header(None, alias="user-agent"),
            x_device_type: str | None = Header(None, alias="X-Device-Type"),
        ):
            device_context = get_device_context_from_request(user_agent, x_device_type)
            builder = A2UIBuilder(device_context)
            ...
    """
    return detect_device_context(
        user_agent=user_agent,
        device_type_header=x_device_type,
    )


def is_mobile_device(user_agent: str | None = None) -> bool:
    """Quick check if request is from a mobile device"""
    if not user_agent:
        return False
    parsed = parse_user_agent(user_agent)
    return parsed.is_mobile


def is_tablet_device(user_agent: str | None = None) -> bool:
    """Quick check if request is from a tablet device"""
    if not user_agent:
        return False
    parsed = parse_user_agent(user_agent)
    return parsed.is_tablet


def is_touch_device(user_agent: str | None = None) -> bool:
    """Quick check if request is from a touch device (mobile or tablet)"""
    if not user_agent:
        return False
    parsed = parse_user_agent(user_agent)
    return parsed.is_mobile or parsed.is_tablet
