# Design Summary — FloatMD

**Design doc**: `/tmp/grok-root/grok-design-doc-a12fc8f0.md`  
**Status**: Draft (greenfield)  
**Date**: 2026-08-28

## What was produced

A full design specification for **FloatMD**, a Linux-first floating desktop utility that combines:

1. Markdown note editing/persistence (`.md` files)
2. Beautified Display-mode preview
3. OCR (screenshot / paste / drag-drop)
4. Short-context AI via OpenAI-compatible APIs (`reply` vs `replace` JSON)

## Stack chosen

| Layer | Choice |
|-------|--------|
| Shell | Tauri 2 (frameless, always-on-top, tray, hotkey) |
| UI | Vue 3 + TypeScript + Vite + Pinia |
| Edit | CodeMirror 6 |
| Preview | markdown-it + Shiki/hljs + KaTeX + Mermaid + DOMPurify |
| OCR MVP | Tesseract.js (`chi_sim` + `eng`); PaddleOCR sidecar later |
| AI | Configurable baseURL/model/key; no tools; no long context; no streaming in v1 |
| Secrets | OS keychain / Tauri Stronghold |

## Document sections included

Overview, Background & Motivation, Goals & Non-Goals, Proposed Design (architecture + sequence Mermaid diagrams), API/Interface surface, Data Model, Alternatives Considered (≥2 with trade-offs), Security & Privacy, Observability, Rollout Plan, **Key Decisions**, Open Questions, Risks, References, and an ordered **PR Plan** (11 PRs from scaffold → Linux alpha → stretch OCR/streaming/platforms).

## Notable product defaults proposed (pending Open Questions)

- Dual mode Edit ↔ Display (not WYSIWYG)
- `replace` applies to **selected lines only**
- Default notes path proposal: `~/.local/share/floatmd/notes`
- Autosave debounce ~500–800 ms
- zh-CN + en UI
- Linux primary; Windows/macOS stretch

## Open questions highlighted for the user

Default notes path, tray vs always-visible first run, empty-selection `replace` behavior, confirm-on-replace, OCR engine priority for Chinese users, in-app snip vs OS paste, transparency, tabs vs single-note switcher, chat history retention, cross-platform timeline, HTML passthrough, hotkey defaults.
