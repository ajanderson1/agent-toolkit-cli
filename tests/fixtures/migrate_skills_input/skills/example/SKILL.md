---
apiVersion: agent-toolkit/v1alpha2
metadata:
  name: example
  description: A combined description used by both harness and CLI today.
  lifecycle: experimental
  notes: |
    argument-hint: <filename>
    Other notes go here.
spec:
  origin: first-party
  vendored_via: none
  harnesses: [claude, pi]
---

# example

Body text.
