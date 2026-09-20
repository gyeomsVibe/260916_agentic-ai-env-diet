"""Error taxonomy for U13 isolation and promotion."""

from __future__ import annotations


class IsolationError(RuntimeError):
    """Base error for isolation, staging, and promotion boundaries."""

    def __init__(self, message: str, *, error_class: str = "ISOLATION_ERROR") -> None:
        super().__init__(message)
        self.message = message
        self.error_class = error_class


class PathSecurityError(IsolationError):
    """Base error for path traversal, escape, and path syntax violations."""

    def __init__(self, message: str, *, error_class: str = "PATH_SECURITY_ERROR") -> None:
        super().__init__(message, error_class=error_class)


class PathTraversalError(PathSecurityError):
    """Raised when a path attempts '..' traversal escape."""

    def __init__(self, message: str = "PATH_TRAVERSAL_ESCAPE") -> None:
        super().__init__(message, error_class="PATH_TRAVERSAL_ESCAPE")


class PathOutsideRootError(PathSecurityError):
    """Raised when a canonical path resolves outside the leased root."""

    def __init__(self, message: str = "PATH_OUTSIDE_ROOT") -> None:
        super().__init__(message, error_class="PATH_OUTSIDE_ROOT")


class ReparsePointError(PathSecurityError):
    """Raised when symlink, junction, or reparse point is encountered."""

    def __init__(self, message: str = "REPARSE_POINT_DETECTED") -> None:
        super().__init__(message, error_class="REPARSE_POINT_DETECTED")


class UncPathError(PathSecurityError):
    """Raised when UNC or network path is specified."""

    def __init__(self, message: str = "UNC_PATH_FORBIDDEN") -> None:
        super().__init__(message, error_class="UNC_PATH_FORBIDDEN")


class AlternateDataStreamError(PathSecurityError):
    """Raised when an NTFS alternate data stream (ADS) is detected."""

    def __init__(self, message: str = "ALTERNATE_DATA_STREAM_FORBIDDEN") -> None:
        super().__init__(message, error_class="ADS_FORBIDDEN")


class CaseAliasError(PathSecurityError):
    """Raised on case-folding collisions or on-disk case mismatches."""

    def __init__(self, message: str = "CASE_ALIAS_COLLISION") -> None:
        super().__init__(message, error_class="CASE_ALIAS_COLLISION")


class ScopeExpansionError(IsolationError):
    """Raised when changes exceed leased resource paths/roots."""

    def __init__(self, message: str = "SCOPE_EXPANSION_FORBIDDEN") -> None:
        super().__init__(message, error_class="SCOPE_EXPANSION")


class SourceDivergenceError(IsolationError):
    """Raised when the base source diverges before promotion (TOCTOU)."""

    def __init__(self, message: str = "BASE_DIVERGED") -> None:
        super().__init__(message, error_class="BASE_DIVERGED")


class SourceMutationError(IsolationError):
    """Raised when source directory is mutated during copy or dry-run."""

    def __init__(self, message: str = "SOURCE_MUTATION_DETECTED") -> None:
        super().__init__(message, error_class="SOURCE_MUTATION")


class StaleFenceOrReceiptError(IsolationError):
    """Raised on stale fencing token or missing/invalid PASS receipt."""

    def __init__(self, message: str = "STALE_FENCE_OR_RECEIPT") -> None:
        super().__init__(message, error_class="STALE_FENCE_OR_RECEIPT")


class UnresolvedEffectError(IsolationError):
    """Raised when unresolved effects (UNKNOWN/INTENDED/FAILED) block promotion."""

    def __init__(self, message: str = "UNRESOLVED_EFFECT") -> None:
        super().__init__(message, error_class="UNRESOLVED_EFFECT")


class PatchHashMismatchError(IsolationError):
    """Raised when content-addressed patch or bundle hash does not match."""

    def __init__(self, message: str = "PATCH_HASH_MISMATCH") -> None:
        super().__init__(message, error_class="PATCH_HASH_MISMATCH")


class UntrackedOverwriteError(IsolationError):
    """Raised when promotion would overwrite an existing untracked file."""

    def __init__(self, message: str = "UNTRACKED_OVERWRITE_FORBIDDEN") -> None:
        super().__init__(message, error_class="UNTRACKED_OVERWRITE")


class ConcurrentOwnershipError(IsolationError):
    """Raised when another attempt or lease concurrently owns the target file."""

    def __init__(self, message: str = "CONCURRENT_OWNERSHIP_CONFLICT") -> None:
        super().__init__(message, error_class="CONCURRENT_OWNERSHIP")


class LiveMutationProhibitedError(IsolationError):
    """Raised when live promotion, live delete, or live overwrite is attempted."""

    def __init__(self, message: str = "LIVE_MUTATION_PROHIBITED") -> None:
        super().__init__(message, error_class="LIVE_MUTATION_PROHIBITED")


class GitWorktreeError(IsolationError):
    """Raised when git command or worktree operation fails."""

    def __init__(self, message: str = "GIT_WORKTREE_ERROR") -> None:
        super().__init__(message, error_class="GIT_WORKTREE_ERROR")


class ExternalWriteDetectedError(IsolationError):
    """Raised when an external write is detected outside the staging boundary."""

    def __init__(
        self,
        message: str = "EXTERNAL_WRITE_DETECTED",
        *,
        effect_state: str = "UNKNOWN",
        changed_paths: Sequence[str] | None = None,
    ) -> None:
        super().__init__(message, error_class="EXTERNAL_WRITE_DETECTED")
        self.effect_state = effect_state
        self.changed_paths: list[str] = list(changed_paths or [])


class WatchScanUnavailableError(IsolationError):
    """Raised when a watched root or file cannot be enumerated reliably."""

    def __init__(self, message: str = "WATCH_SCAN_UNAVAILABLE") -> None:
        super().__init__(message, error_class="WATCH_SCAN_UNAVAILABLE")
        self.effect_state = "UNKNOWN"
