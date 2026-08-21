//! Envelope `ts` clock (schemas/README.md: CLOCK_MONOTONIC seconds).

/// Monotonic now, in seconds, comparable across processes on one machine.
#[cfg(unix)]
pub fn mono_now() -> f64 {
    let mut ts = libc::timespec {
        tv_sec: 0,
        tv_nsec: 0,
    };
    // Safety: clock_gettime with a valid pointer; CLOCK_MONOTONIC always exists.
    unsafe {
        libc::clock_gettime(libc::CLOCK_MONOTONIC, &mut ts);
    }
    ts.tv_sec as f64 + ts.tv_nsec as f64 / 1e9
}

/// Windows fallback for local development only: monotonic within this
/// process, NOT comparable across processes. The bus never ships on
/// Windows — ares is Linux — so cross-process latency math is a
/// Linux-only concern and tests that need it are cfg(unix).
#[cfg(not(unix))]
pub fn mono_now() -> f64 {
    use std::sync::OnceLock;
    use std::time::Instant;
    static START: OnceLock<Instant> = OnceLock::new();
    START.get_or_init(Instant::now).elapsed().as_secs_f64()
}
