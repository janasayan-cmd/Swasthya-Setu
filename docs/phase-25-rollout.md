# HealthSetu — Phase 25: Controlled Feature Rollout Strategies

## 1. Rollout Strategies

HealthSetu supports four targeted rollout models to govern feature exposure safely without exposing unvalidated clinical workflows to production patients:

1. **`DISABLED`**: Feature unavailable to all actors regardless of context.
2. **`ENABLED`**: Globally operational across all configured environments.
3. **`ALLOWLIST`**: Restricts activation to specific `user_id`s, `organization_id`s, or `facility_id`s.
4. **`ORGANIZATION_ROLLOUT`**: Clinical department / hospital pilot programs where an entire healthcare organization is enrolled.
5. **`PERCENTAGE_ROLLOUT`**: Gradual cohort ramp-up (e.g. 5% → 20% → 50% → 100%).

---

## 2. Deterministic Hash Evaluation (TRD Sec 21)

To prevent users from experiencing flickering feature states between requests, percentage rollouts use cryptographic SHA-256 bucket allocation:

$$\text{bucket} = \text{int}\Big(\text{SHA256}\big(\text{flag\_name} + \text{":"} + \text{stable\_id}\big)\Big) \pmod{100}$$

Where `stable_id` selects the highest available organizational context:
$$\text{stable\_id} = \text{organization\_id} \lor \text{facility\_id} \lor \text{clinician\_id} \lor \text{user\_id} \lor \text{patient\_id}$$

If no stable entity identifier is provided in the evaluation context, the rollout evaluator defaults to `False` (fail-closed).

---

## 3. Best Practices for Clinical Rollouts (TRD Sec 20)

- **Prefer Organization Allowlists**: When testing emergency triage or medication safety updates, avoid arbitrary percentage rollouts over patients. Restrict rollout to specific hospital partner pilot facilities (`allowlist_facilities` or `allowlist_organizations`).
- **Never Override Authorization**: An actor who receives `is_enabled == True` must still be thoroughly authenticated, authorized, and consented for the specific patient resource.
