# PhotoAgent safety and recovery

Implemented v2.1/v2.2 behavior, 2026-11-08. Evidence and unverified limits are separated
in [TESTING.md](TESTING.md). This application never permanently deletes photographs.

## Approval and verification

Before confirmation, a frozen plan enumerates every concrete source, keeper and
quarantine/restore destination. A scrollable read-only dialog displays all entries,
full SHA-256 values and source identities. Confirmation applies to that plan.
RAW sources require entering RAW; legacy restore requires another individual warning.
XMP sidecars stay in place and are shown in the individual-operation warning.

Bulk eligibility requires decoded EXACT files, neither member RAW, both in the same
selected root, and no XMP sidecar for either member. Copies across roots require
individual review, because they may be deliberate backups. VISUAL, DERIVATIVE and
SIMILAR_CAPTURE never qualify for bulk operations. Hash collisions in visual matching
are expected. Heuristic quality does not prove image value or authorize an operation.

Every file has device/inode, size, nanosecond mtime/ctime and full SHA-256 from stable
reads. Both source and keeper are reverified before moving. EXACT also requires mutual
SHA-256 equality. Source/keeper aliases, changed roots, path escapes, symlinks and
Windows reparse points/junctions are rejected. Directory ancestors are checked before
normalization or resolution; parent traversal is rejected. Quarantine descendants
are excluded even when explicitly selected as scan roots. Missing roots produce an
incomplete scan. Unsafe/ambiguous operations fail closed.

Snapshot ctime comes consistently from fstat. Python 3.12 Windows path stat and handle
fstat can expose different ctime meanings; path comparison uses identity, size and
mtime, while stable handle reads also compare ctime and the full content hash.

## Native no-overwrite adapter

Windows uses an open source handle and SetFileInformationByHandle(FileRenameInfo)
with ReplaceIfExists=False. Source/keeper handles deny writers; ancestor directory
handles deny directory replacement through verification and rename. Linux uses
O_NOFOLLOW directory descriptors and renameat2(RENAME_NOREPLACE), with a final
source-name identity check. Parent creation also uses pinned handles/directory fds.
Existing destinations, including a destination created after confirmation, survive.
Unsupported platforms/filesystems and cross-device renames fail; there is no
copy/delete or ordinary-rename fallback.

Platform references: [Microsoft FILE_RENAME_INFO](https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_rename_info)
and [Linux renameat2](https://man7.org/linux/man-pages/man2/rename.2.html).

## Journal protocol

- One OS lock permits one history writer. Other instances may scan but cannot save
  settings, import, recover, quarantine or restore.
- Version 1 JSON uses one manifest per operation, UUID temporary files, flush/fsync
  before atomic replacement and directory fsync on Linux. Each manifest retains
  its state transitions and failure details. Windows does not claim directory-fsync
  or physical power-loss durability.
- Intent is persisted after verification and before native rename. A failed intent
  write prevents movement. Cancellation is checked each hash block and between
  files. After intent, finish the active operation or leave it for recovery.
- Successful movement is verified before completion is written. A failed completion
  write leaves intent; there is no unverified automatic rollback.
- Recovery checks root identity and both paths. One matching source means not_moved;
  one matching destination means complete. Both/neither path, changed bytes/identity,
  missing media or redirected paths become blocked, with evidence preserved. The
  blocked state can be rechecked after the media returns. New plans are blocked
  until pending operations reconcile.
- Restore verifies the quarantined identity and full bytes, freezes another plan,
  confirms it and uses the same adapter/journal. A new original at the restore path
  is never overwritten. Original and restore manifests are retained.
- Legacy JSON is validated and backed up byte-for-byte before idempotent import.
  Its old content is unverifiable; restoration requires explicit individual approval
  of a newly measured snapshot. Corrupt history never silently becomes empty.

If recovery is blocked, keep manifests, backups and both file paths. Reconnect the
original storage and retry the action/restart to re-run reconciliation. Do not
manually erase the journal or fall back to the old prototype to force a move.

## Resource policy and limits

### Incremental index trust boundary (v2.2)

SQLite is a disposable cache, not permission to move a file. Every warm scan reads
the complete file and compares a new stable SHA-256 snapshot before using cached
dimensions/hashes. Metadata-only shortcuts are not used. Fingerprints include a
decoder/dependency version and checksum. Invalid entries are recomputed; checksums
detect accidental damage, not malicious tampering by an account with write access.

Preparation independently re-inspects source/keeper bytes, decode status and RAW
classification. Native execution still verifies full snapshots through pinned
handles and requires frozen-plan approval. Forged cache eligibility cannot grant
bulk permission. Partial scans are review-only; cancellation removes partial pairs.

Absence reconciliation requires successful enumeration and unchanged root identity.
Offline libraries retain records. Replaced media gets another root identity without
sweeping old records. Rename detection only changes index metadata. Symlink/junction
and quarantine exclusions apply to cold and warm scans.

The JSON journal remains authoritative and preserves its version-1 wire shape.
SQLite projection failures do not falsely report completed native moves as undone.
Affected paths and dependent matches are invalidated after operations, including
partial failures, and reconciled on restart. No recovery information exists only
in SQLite. Corrupt/newer indexes are retained and bypassed with private temporary
indexes. Corrupt operation history still blocks quarantine and restoration.

Index storage is intended for a local filesystem. Network/redirected-home WAL
behavior is unverified. Scan history grows on disk; frozen operation plans can grow
in memory even though indexed scanning and result browsing use bounded buffers.

### Decoder and platform limits

Original decoding runs in a disposable subprocess, at most 100 megapixels and
60 seconds per request. Timeout/cancellation kills and reaps the child. Decode
errors/crashes retain binary exact matching but disqualify bulk candidates. This is
process isolation, not an OS security sandbox or a strict process-memory cap.

Windows native moves/conflicts/handle pinning are covered with synthetic fixtures.
Native Linux, valid RAW decoding and real disconnected/removable media are unverified.
Network filesystems and hostile concurrent namespace mutation are outside the tested
contract. In particular Linux has no general rename-by-file-handle primitive: another
process can race the source-name check, or move an open ancestor directory. Do not
change the library concurrently during a plan. Post-operation verification detects
mismatch and blocks recovery but cannot make such races atomic. OS filesystem calls
may block until the OS returns; cancellation does not impose a hard I/O deadline.

Termination tests demonstrate restart reconciliation, not physical power-loss
resilience. Keep independent backups. No automatic operation touches an XMP sidecar,
and byte-preserving movement keeps EXIF/ICC and edited image content intact.
