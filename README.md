# AutoDev AI

An autonomous, multi-agent software engineering workspace engineered to generate, execute, and validate Python code pipelines.

## Overview
AutoDev AI addresses the inherent unreliability and hallucination rates in standard Large Language Model (LLM) code generation. By implementing a sophisticated multi-agent orchestration framework, the system dynamically routes tasks between specialized generation and Quality Assurance agents. It replicates a production-level engineering workflow where code is iteratively synthesized, locally sandboxed, executed, and validated prior to deployment.

## Core Architecture & Features
* **Multi-Agent Orchestration:** Utilizes a directed workflow architecture to isolate code generation and validation roles, ensuring strict adherence to logical requirements.
* **Sandboxed Execution Harness:** Code artifacts are securely executed within a local Python subprocess environment to intercept runtime exceptions and syntax anomalies automatically.
* **Human-in-the-Loop (HITL) Validation:** Implements a mandatory authorization gate, presenting verified, executable code to the user for final review and approval.
* **Semantic Caching via Vector Storage:** Approved code artifacts are indexed into a Supabase pgvector database, drastically reducing latency and computational overhead for structurally similar subsequent requests.
* **Hybrid LLM Engine:** Integrates a locally fine-tuned, parameter-efficient model (Mistral via QLoRA) for high-density generation tasks, augmented by external APIs for specialized routing.

## Technical Stack
* **Orchestration & Logic:** Python, CrewAI, LangChain
* **Inference Models:** Mistral-7B (QLoRA Fine-Tuned), Gemini API
* **Infrastructure & Backend:** FastAPI, Python Subprocess module
* **Data Persistence & Vector Storage:** Supabase, pgvector
* **Client Interface:** Streamlit

## Project Context
This repository serves as the Minimum Viable Product (MVP) submission for the AI Engineer Associate application at Dafinitiq AI, demonstrating scalable architectural patterns and production-ready AI integration.
