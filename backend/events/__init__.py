"""Internal Event System for ErgoVigilance.

Provides a lightweight synchronous EventBus for backend-to-backend
communication. Events are immutable dataclasses published through
the bus. No async, no external libraries.
"""
