# Agent Architecture & Instructions System

This document outlines the global rules, orchestration policies, and agent specifications for Tark (Software Engineering Workflow Coach).

## System Prompts Loading System
The system loads agent instructions from `prompts/*.txt` files at startup. If a file is missing, it falls back to the default inline definition.
The prompts folder contains:
- `coordinator.txt`: Classifies input and orchestrates turns.
- `bug_coach.txt`: Guides the BUG workflow steps.
- `feature_coach.txt`: Guides the FEATURE workflow steps.
- `meeting_coach.txt`: Guides the MEETING/PLANNING workflow steps.
- `general_advisor.txt`: Guides the GENERAL_ENGINEERING_QUESTION workflow steps.
- `test_strategy.txt`: Formulates BDD / TDD tests.
- `observability.txt`: Suggests logging, tracing, metrics, and profiling.
- `skeptic.txt`: Challenges weak assumptions and prevents shortcutting.
- `judge.txt`: Maintains checklist progress and decides step status.

## General Decision Policy (Ask Questions Only When Necessary)
All agents, especially the `GeneralAdvisorAgent`, must follow these rules:
1. **Direct Answer**: If user input is narrow and clear, answer directly. Do not ask clarifying questions just because more context could exist.
2. **Clarification Threshold**: Ask questions only if the missing information would lead to a wrong/unsafe answer, or output too generic to be useful.
3. **Progressive Refinement**: If partially vague, give the best immediate answer first, followed by 1–3 high-value questions.
4. **Zero-Block UX**: Do not block workflow progression when input is vague. Print the best-practice guidelines and move forward rather than looping back.
