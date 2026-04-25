#!/bin/bash
# Convert markdown to EPUB using pandoc

INPUT_FILE="/Users/link/Downloads/Telegram Desktop/波动率交易_第二版-zh-CN/translation.md"
OUTPUT_FILE="/Users/link/Downloads/Telegram Desktop/波动率交易_第二版.epub"

# Create a cover page or metadata
cat > /tmp/book_metadata.yaml << 'EOF'
---
title: "Volatility Trading, Second Edition"
subtitle: "波动率交易（第二版）"
author: "Euan Sinclair"
description: "本书是关于波动率交易的经典著作，涵盖了期权定价、波动率测量、对冲策略、资金管理等核心内容。"
lang: zh-CN
date: 2024-03-22
rights: "仅供学习交流使用"
---
EOF

echo "Converting Markdown to EPUB..."
pandoc \
  /tmp/book_metadata.yaml \
  "$INPUT_FILE" \
  -o "$OUTPUT_FILE" \
  --from markdown \
  --to epub \
  --epub-chapter-level=1 \
  --toc \
  --toc-depth=2 \
  --metadata title="波动率交易（第二版）" \
  --metadata author="Euan Sinclair" \
  --metadata language="zh-CN" \
  --css=/dev/null \
  2>&1

if [ $? -eq 0 ]; then
  echo "✓ EPUB created successfully!"
  echo "File: $OUTPUT_FILE"
  ls -lh "$OUTPUT_FILE"
else
  echo "✗ Conversion failed"
fi
