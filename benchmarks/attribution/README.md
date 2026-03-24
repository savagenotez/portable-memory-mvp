# Attribution

This folder contains phrase-saver attribution outputs.

## Purpose

These reports explain which hybrid-added lines restore expected phrases that compression mode missed.

## Why this matters

Hybrid is currently the best balance mode.
To improve the system further, we need to know which added lines actually save recall.

## Current outputs

- JSON attribution report
- Markdown attribution report

## Future direction

- use phrase-saver lines to build a phrase-restorer policy
- distinguish durable savers from situational savers
- score saver lines by restored phrases per byte
