# Future FL partition plan — proposed, pending approval

There is one vehicle and no natural client boundary. Client IDs below are simulated experiment identifiers, never a claim that a source file is a client. No full partition is emitted by B3.

Precondition: verify source checksums; parse/validate; exclude or otherwise handle the shared tail only after DEC-002; make a per-source purged temporal train/val/test split only after DEC-008. The B2 proposal is seed 42, 70/15/15 and 1% purge gap. Fit scalers on train only; reset temporal state at source/split boundaries; do not oversample before split; retain `(source_file, source_line)` identity to audit overlap.

| Proposed experiment | Simulated IDs | Construction after global split | Purpose |
|---|---|---|---|
| IID | `iid-01...iid-K` | seeded stratified allocation across label/type, preserving immutable global split | baseline fairness |
| Label-skew Non-IID | `noniid-label-01...K` | seeded Dirichlet or explicit class proportions, minimum-per-class documented | heterogeneous labels |
| Temporal/source-skew Non-IID | `noniid-time-01...K` | contiguous eligible windows per source, never crossing split boundaries | deployment-like drift |

Every future partition manifest must state approved decision IDs, dataset/sample hash, seed and RNG version, client ID, row counts by split/label/type/provenance, source-line range/list hash, shared-tail policy, purge parameters, and overlap checks. It must prove no observation identity occurs in two global splits or clients where the experiment forbids it. Repeated CAN payload content is not alone leakage.

Required approvals: A2/A3/mentor decide DEC-004 client definition and Non-IID scenario; DEC-003 task target; mentor DEC-008 fractions; A2/A3/mentor DEC-002 tail policy. Until then this document is a plan, not an executable production partition.
