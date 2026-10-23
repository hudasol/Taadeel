# Security and responsible use

Report a vulnerability by opening a private security advisory on this repository, or by contacting the maintainer through the address on the GitHub profile. Please do not post details publicly before a fix is available.

Scope notes: the service is read only, holds no user accounts and sends no data to third parties. The ingestion tools only contact hosts marked `permitted` in `sources.toml`, and they stop on any block. The container runs as a non root user.
