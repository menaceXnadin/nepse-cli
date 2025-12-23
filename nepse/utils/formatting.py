"""
Formatting utilities for numbers and currency.
"""


def format_number(num) -> str:
    """
    Format numbers with appropriate units (K, M, B) or with commas.
    For portfolio display, use commas for better readability.
    
    Args:
        num: Number to format (can be string, int, or float)
        
    Returns:
        Formatted string
    """
    try:
        num = float(str(num).replace(',', ''))
        
        # For whole numbers, don't show decimal places
        if num == int(num):
            return f"{int(num):,}"
        else:
            return f"{num:,.2f}"
    except (ValueError, AttributeError, TypeError):
        return str(num)


def format_number_compact(num) -> str:
    """
    Format large numbers with K, M, B suffixes for compact display.
    
    Args:
        num: Number to format
        
    Returns:
        Formatted string with suffix
    """
    try:
        num = float(str(num).replace(',', ''))
        if num >= 1_000_000_000:
            return f"{num / 1_000_000_000:.2f}B"
        elif num >= 1_000_000:
            return f"{num / 1_000_000:.2f}M"
        elif num >= 1_000:
            return f"{num / 1_000:.2f}K"
        else:
            return f"{num:.2f}"
    except (ValueError, AttributeError, TypeError):
        return str(num)


def format_rupees(amount) -> str:
    """
    Format amount as rupees with proper comma placement.
    Uses Indian numbering system (lakhs/crores).
    
    Args:
        amount: Amount to format (can be string, int, or float)
        
    Returns:
        Formatted rupee string
    """
    try:
        amount = float(str(amount).replace(',', ''))
        
        # For display in tables, use standard comma formatting
        # Remove decimal places if the amount is a whole number
        if amount == int(amount):
            return f"Rs. {int(amount):,}"
        else:
            return f"Rs. {amount:,.2f}"
    except (ValueError, AttributeError, TypeError):
        return f"Rs. {amount}"


def format_indian_rupees(amount) -> str:
    """
    Format amount in Indian numbering system (lakhs, crores).
    E.g., 1,00,000 instead of 100,000
    
    Args:
        amount: Amount to format
        
    Returns:
        Formatted string in Indian style
    """
    try:
        amount = float(str(amount).replace(',', ''))
        
        # Convert to integer if it's a whole number
        if amount == int(amount):
            amount = int(amount)
            
        # Indian numbering system
        s = str(amount)
        if '.' in s:
            integer_part, decimal_part = s.split('.')
        else:
            integer_part = s
            decimal_part = None
        
        # Reverse the integer part
        integer_part = integer_part[::-1]
        
        # Add commas: first after 3 digits, then after every 2 digits
        result = []
        for i, digit in enumerate(integer_part):
            if i == 3 or (i > 3 and (i - 3) % 2 == 0):
                result.append(',')
            result.append(digit)
        
        # Reverse back
        formatted = ''.join(result[::-1])
        
        # Add decimal part if exists
        if decimal_part:
            formatted = f"{formatted}.{decimal_part[:2]}"
        
        return f"Rs. {formatted}"
    except (ValueError, AttributeError, TypeError):
        return f"Rs. {amount}"


def format_percentage(value, decimals: int = 2) -> str:
    """
    Format a value as percentage.
    
    Args:
        value: Numeric value to format
        decimals: Number of decimal places
        
    Returns:
        Formatted percentage string
    """
    try:
        value = float(value)
        return f"{value:.{decimals}f}%"
    except (ValueError, TypeError):
        return str(value)


def format_change(current, previous) -> str:
    """
    Calculate and format the change between two values.
    
    Args:
        current: Current value
        previous: Previous value
        
    Returns:
        Formatted change string with +/- and percentage
    """
    try:
        current = float(str(current).replace(',', ''))
        previous = float(str(previous).replace(',', ''))
        
        if previous == 0:
            return "N/A"
        
        change = current - previous
        change_percent = (change / previous) * 100
        
        sign = "+" if change >= 0 else ""
        return f"{sign}{change:,.2f} ({sign}{change_percent:.2f}%)"
    except (ValueError, TypeError):
        return "N/A"


