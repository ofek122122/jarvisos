//! jv-act — the ONLY service allowed to mutate system state
//! (CLAUDE.md invariant 3). Every line here is subject to human review
//! before it runs anywhere; see PHASE2-STATUS.md REVIEW-REQUIRED.

pub mod audit;
pub mod exec;
pub mod registry;
pub mod service;
