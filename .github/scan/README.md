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
download errors also fail the job. The image-only exception below is applied to
the saved scan before uploading the report and enforcing the finding policy.

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

## Image-only exception: pip's setuptools SBOM

`trivy-image-ignore.rego` suppresses only CVE-2025-47273, CVE-2026-59890 and
GHSA-xmj3-9gf7-h52w for the `setuptools` 70.3.0 SBOM component with PURL and
BOMRef `pkg:pypi/setuptools@70.3.0` in the inspected linux/amd64 base-image
layer. Matching its DiffID ensures a changed layer is not silently ignored.
Other packages, versions, IDs, layers and filesystem findings remain visible.

On 2026-11-16 image
`sha256:8bcafe42369c76506c4124f8950d64378e72347fbdc92d9f090a4e033579c938`
contained no installed or importable `setuptools`. Its `ensurepip` pip 26.2.2
wheel contained no `setuptools` files, while installed pip 26.3 included a
vendored `pkg_resources` module. [pip's vendor documentation](https://github.com/pypa/pip/blob/26.3/src/pip/_vendor/README.rst)
describes retaining only `pkg_resources` from setuptools. The affected paths
are [PackageIndex](https://github.com/pypa/setuptools/security/advisories/GHSA-5rjg-fvgr-3xxf),
[macOS sdist manifest processing](https://github.com/pypa/setuptools/security/advisories/GHSA-h35f-9h28-mq5c),
and [Windows legacy wheel installation](https://github.com/pypa/setuptools/security/advisories/GHSA-xmj3-9gf7-h52w),
not the retained `pkg_resources` module. The bundled wheel also contains other
vendored packages; the policy does not exclude them.

Reinspect the actual image, installed files, bundled wheels and advisories when
the base layer, pip, platform or scanner changes. Remove the exception when it
is no longer necessary. A different platform or layer requires its own evidence.
