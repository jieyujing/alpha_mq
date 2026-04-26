#!/usr/bin/env python3
"""
_restore_option_terms.py - Restore English option terminology
"""

import re

def restore_option_terms(input_file, output_file):
    """Replace Chinese option terms with English equivalents"""

    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # Define replacements - order matters for overlapping terms
    replacements = [
        # Complex patterns first (avoid double replacement)
        (r'看涨期权', 'call option'),
        (r'看跌期权', 'put option'),
        (r'看涨', 'call'),
        (r'看跌', 'put'),

        # Other option terms
        (r'期权\s*（\s*金融\s*）', 'options (finance)'),
        (r'期权定价', 'Option Pricing'),
        (r'期权', 'option'),

        # Strike and expiry
        (r'行权价', 'strike'),
        (r'到期日', 'expiry'),

        # Greeks (ensure they stay English)
        (r'[Dd]elta', 'Delta'),
        (r'[Gg]amma', 'Gamma'),
        (r'[Vv]ega', 'Vega'),
        (r'[Tt]heta', 'Theta'),
        (r'[Rr]ho', 'Rho'),

        # Common terms
        (r'标的资产', 'underlying'),
        (r'标的', 'underlying'),
        (r'隐含波动率', 'implied volatility'),
        (r'已实现波动率', 'realized volatility'),
        (r'对冲', 'hedge'),
        (r'多头', 'long'),
        (r'空头', 'short'),
    ]

    # Apply replacements
    for pattern, replacement in replacements:
        content = re.sub(pattern, replacement, content)

    # Write output
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"Processed and saved to: {output_file}")

if __name__ == "__main__":
    input_file = "/Users/link/Downloads/Telegram Desktop/波动率交易_第二版-zh-CN/translation.md"
    output_file = "/Users/link/Downloads/Telegram Desktop/波动率交易_第二版-zh-CN/translation_en_terms.md"
    restore_option_terms(input_file, output_file)
