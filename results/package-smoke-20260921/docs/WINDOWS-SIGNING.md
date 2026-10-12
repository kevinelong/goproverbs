# Windows signing for local builds

Status, September 20: workflow prepared; no executable signed yet. No code-signing
certificate was found in Kevin's CurrentUser/My or LocalMachine/My stores.
SignTool 10.0.26100.0 and .NET 8 x64 are installed. Azure CLI and a signing account
are not configured. Enrollment is the outstanding dependency.
The user confirmed they have neither an Azure subscription nor an existing
signing certificate/service. No browser session was available for assisted signup.

Validation completed: `-InspectBuild` compiled successfully and enumerated nine
executables (seven test executables), without executing them. SignTool rejected
the unsigned application as expected. The workflow rejected a missing enrollment
configuration before compiling or running. PowerShell syntax validation passed.
Signing and signed execution remain untested until enrollment is complete.

## Intended route

Azure Artifact Signing Basic with a **Public Trust** certificate profile is the
proposed service. Microsoft's listed price is USD 9.99/month for 5,000 signatures,
then USD 0.005 per extra signature. Actual subscription pricing/taxes apply.
No subscription, paid resource, or identity-validation request has been created.

Individual Public Trust enrollment is available in the USA and Canada. It needs
an Azure paid subscription (for example pay-as-you-go; free/trial subscriptions
are not supported) with an Individual billing account, matching legal identity
details, and verification completed by the account owner in Microsoft's portal.
Do not put government ID, passwords, or private keys in this repository or chat.
Use Public Trust, not Public Trust Test or Private Trust, for this purpose.

Once the Azure account/subscription is selected and the paid service authorized:

1. Create an Artifact Signing Basic account in West US 2 (or another supported
   region); register Microsoft.CodeSigning if necessary.
2. Complete public identity validation in the Azure portal.
3. Create a Public Trust profile and assign the signing user the Artifact Signing
   Certificate Profile Signer role at that profile's scope. Enrollment also needs
   the identity-verifier role; resource management uses separate Azure permissions.
4. Install Microsoft's Artifact Signing Client Tools and Azure CLI. Sign in with
   `az login` as the signing user. The SignTool client uses DefaultAzureCredential.
5. Copy the two templates from `scripts/` to
   `%LOCALAPPDATA%/goproverbs-signing/config.json` and `metadata.json`. Fill in the
   actual account, profile, x64 dlib path, and endpoint matching the account region.
   The templates contain placeholders and will be rejected as configuration.

The configuration lives outside the repository. It contains paths/account names,
not credentials. SDK and signing DLL architectures must match (x64 here).

## Commands

Run in PowerShell 7, using the enrolled Windows account:

```powershell
# Compile and inspect only; no signing account needed; never executes artifacts.
pwsh -NoProfile -File scripts/Invoke-SignedCargo.ps1 -InspectBuild

# Build, sign every executable, verify, then run compiled unit/integration tests.
pwsh -NoProfile -File scripts/Invoke-SignedCargo.ps1 -Action Test

# Produce signed release binaries, without running them.
pwsh -NoProfile -File scripts/Invoke-SignedCargo.ps1 -Action Build -Release

# From PowerShell, pass application arguments as an array.
& ./scripts/Invoke-SignedCargo.ps1 -Action Run -Release -ProgramArguments @('--size','9','--suggest','D4')
```

This workflow uses `target/signed`, leaving the ordinary build directory alone.
It obtains executable paths from Cargo's JSON output, signs all executables before
launching any, and verifies Authenticode trust and RSA signatures. This includes
the application spawned by integration tests. A signing or verification failure
stops execution. Valid existing signatures are verified and reused to avoid
charging for unchanged files; a rebuild changes the bytes and needs a new signature.
New signatures receive an RFC3161 timestamp.

Test mode runs compiled unit/integration test executables directly and does not
run rustdoc doctests. The current crate has no build scripts or external crates;
this workflow does not intercept executables Cargo runs during compilation,
including future build scripts/procedural macros. It does not alter plain
`cargo test`, `cargo run`, machine trust policy, or Smart App Control settings.

A standard Authenticode check cannot guarantee every Windows security decision.
After enrollment, verify one real signed test run and check Code Integrity events
if Windows still blocks it. SmartScreen reputation is a separate mechanism.

## Existing certificate alternative

If a suitable CA-issued RSA certificate is already available, use this config
instead (replace the thumbprint and the provider's RFC3161 timestamp URL):

```json
{
  "Provider": "CertificateStore",
  "SignTool": "C:/Program Files (x86)/Windows Kits/10/bin/10.0.26100.0/x64/signtool.exe",
  "Thumbprint": "REPLACE_WITH_40_HEX_DIGITS",
  "MachineStore": false,
  "TimestampUrl": "REPLACE_WITH_PROVIDER_RFC3161_URL"
}
```

Self-signed certificates do not satisfy Smart App Control's trusted-provider
requirement. This script does not create or install trust roots.

## Sources

- [Smart App Control signing requirements](https://learn.microsoft.com/en-us/windows/apps/develop/smart-app-control/code-signing-for-smart-app-control)
- [Artifact Signing enrollment and identity validation](https://learn.microsoft.com/en-us/azure/artifact-signing/quickstart)
- [SignTool integration and timestamping](https://learn.microsoft.com/en-us/azure/artifact-signing/how-to-signing-integrations)
- [Basic pricing and signature quota](https://learn.microsoft.com/en-us/azure/artifact-signing/how-to-change-sku)
- [Supported Azure subscription types](https://learn.microsoft.com/en-us/azure/artifact-signing/faq)
