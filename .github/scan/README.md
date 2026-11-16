# Trivy security scans

The Scan workflow runs image and filesystem jobs on pull requests to `main`,
pushes to `main`, and the weekly schedule. The existing secret and source scans
retain their push and scheduled events. The image job builds the `service`
Dockerfile target for the checked-out revision and scans OS and application
packages. The filesystem job scans supported manifests, including development
dependencies in `uv.lock`, and configuration files. These checks do not replace
source-code or secret scanning.

Both reports include LOW, MEDIUM, HIGH and CRITICAL findings, including those
without a fix. Any such finding fails its job, including LOW findings. UNKNOWN
severity is outside this policy. Each job uploads its JSON report for 60 days
before evaluating that same report. Scan, report validation, upload and database
download errors also fail the job. No finding exceptions are configured.

The jobs use Trivy 0.76.2 and verify the Linux amd64 archive against the SHA-256
digest in the [immutable release metadata](https://github.com/aquasecurity/trivy/releases/tag/v0.76.2).
The digest protects against later replacement; it does not prove the original
release was safe. Review the [Trivy supply-chain advisory](https://github.com/aquasecurity/trivy/security/advisories/GHSA-69fq-xp46-6x23)
and current advisories when updating. The GitHub-hosted runner, Docker base
images, package sources, vulnerability database and misconfiguration checks
remain separate trusted, dynamically updated dependencies. The workflow does
not grant deployment credentials or persist checkout credentials.

The push trigger for `feature/33-trivy-security-scans` is temporary for CI
verification. Remove it before merging; only the Trivy jobs run on that push.
