# Custom OSS update candidate

The owner-provided Docker inventory shows `python-jobs` and `github-history`
running the same local image ID; `mcp-server` uses a separate local image. The
jobs and MCP application files are baked into their images, while the history
service also uses read-only script bind mounts. The two examined history script
binds match public main snapshot `5b5764a1fe40340823885a6b7b842cdc985fe276`.
Those local scripts are untracked in the runtime checkout and must be preserved.

The checkout's MCP server and two jobs source files differ from that public
snapshot. This alone does not establish which code is inside the running images.
The read-only `compare_custom_sources.py` diagnostic compares four selected
image files with both the runtime checkout and the public snapshot, reporting
only match, difference or unavailable. It does not prove full image provenance or
compare secrets, configuration, dependencies or every source file.

Public changes include stricter MCP argument validation and changes to GitHub
collection and reporting. Candidate update preparation should use an isolated
checkout at the intended public commit and a uniquely tagged image; do not
overwrite the live checkout, the untracked files, or reuse the mutable live image
tag as proof of what was deployed. Review the relevant changes and run focused
tests before any build or deployment.

Because the two jobs-related containers currently share an image, a new build
must not be treated as a one-service change. Select each target explicitly,
preserve its different mounts and dependencies, and verify health independently.
In particular, the history service's read-only bind mounts must not be replaced
or dropped. A new image build, service recreation and any external registry access
remain separate from this read-only diagnosis and must follow the owner's actual
approved execution scope.
