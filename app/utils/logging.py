def log(module: str, message: str, level: str = "INFO"):
    """
    Consistent logging helper.
    """
    # Simple print for now, can be upgraded to logging module later
    icon = "✓" if level == "SUCCESS" else "⚠" if level == "WARNING" else "✗" if level == "ERROR" else "ℹ"
    print(f"[{module}] {icon} {message}")
