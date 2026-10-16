# Release helper TLS profile

The release helpers delegate GitHub API transport to `gh`. The verified profile
below applies to GitHub CLI 2.102.0 built with Go 1.27.1 and the normal
`api.github.com` endpoint. It supplies a way to reject smaller certificate keys
for an individual command while preserving certificate and hostname validation.

## Verify the toolchain

Inspect the exact executable that the helper will use:

```sh
gh --version
go version -m "$(command -v gh)"
```

The first command must identify `gh` 2.102.0; the first line of the second must
identify `go1.27.1` for this verified profile. The `go` command only inspects the
executable's build information. Other toolchain versions need equivalent
verification before this document's key restrictions can be claimed. Older Go
runtimes may ignore settings they do not recognize.

The default client uses Go's `http.DefaultTransport`. In the reviewed runtime,
the default minimum is TLS 1.2, static RSA key exchange is disabled, and default
key agreement uses ephemeral elliptic or hybrid mechanisms. A read-only probe
on 2026-10-08 observed verified ECDSA P-256 certificates with TLS 1.3 AES-128-GCM
and TLS 1.2 ECDHE-ECDSA AES-128-GCM at `api.github.com`. Endpoint observations are
dated evidence; operators should recheck their actual supported environment.

## Apply strict certificate-key verification to one command

From this repository, use its read-only status operation first:

```sh
GH_HOST=github.com GODEBUG=fips140=on python3 scripts/release.py status
```

The assignment applies to this process and its children. `release.py` and the
`release_control.py` GitHub subprocess calls inherit the environment; they do not
remove or replace `GODEBUG`. Use the same prefix when executing an already
reviewed release operation. Keep the normal source, permission and release
checks required by that operation.

For the verified Go runtime, this setting filters every verified certificate
chain to RSA keys of at least 2048 bits, NIST P-256/P-384/P-521, Ed25519 and the
native Go module's supported ML-DSA keys. The TLS cipher and key-exchange filters also
apply. The runtime can consequently reject an endpoint that works with its
ordinary defaults. Fix or review the endpoint configuration rather than
disabling certificate verification.

The shared profile
[verification record](https://github.com/victron-venus/integration-tests/blob/232df66ba8ec59019ee5444090212f256a88b7e6/docs/release-tls-profile.md)
used a temporary CA, synthetic credentials and a
loopback TLS server: a trusted RSA-1024 leaf worked with the ordinary client but
was rejected with `fips140=on`; RSA-2048 worked in both modes. No operator keys,
tokens, trust stores or persistent settings were changed. The public GitHub API
probe also succeeded in the strict profile.

## Scope and limits

This profile covers the helper's TLS connections in the verified environment.
Enterprise hosts, custom API hosts, proxies and custom trust stores need separate
verification of their endpoint identity and certificate chains. This does not
establish the strength of application SSH keys, commit-signing keys or any
other transport. The setting is a Go runtime policy option; using it does not
claim FIPS certification or make FIPS certification an OpenSSF requirement.

Source references:

- [GitHub CLI client construction](https://github.com/cli/cli/blob/v2.102.0/api/http_client.go)
  and [go-gh default transport](https://github.com/cli/go-gh/blob/v2.16.1/pkg/api/http_client.go).
- [Go TLS defaults](https://github.com/golang/go/blob/go1.27.1/src/crypto/tls/defaults.go)
  and [disabled cipher suites](https://github.com/golang/go/blob/go1.27.1/src/crypto/tls/cipher_suites.go).
- [Go certificate-key filters](https://github.com/golang/go/blob/go1.27.1/src/crypto/tls/defaults_fips140.go)
  and [verified-chain enforcement](https://github.com/golang/go/blob/go1.27.1/src/crypto/tls/common.go).
- [OpenSSF Passing criteria](https://www.bestpractices.dev/en/criteria/0), particularly
  `crypto_keylength` and `crypto_pfs`.
