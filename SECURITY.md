# Security notes

Nexo is an early local application. API access uses a random token, loopback binding and host/origin checks. Keep the private access link private. Documents and model outputs are treated as untrusted data; text is rendered without inserting user HTML. Model tools cannot execute shell commands.

The model service is a separately managed Docker container. Access to the Docker daemon itself is powerful; Nexo only accepts local socket/named-pipe contexts and does not change Docker group membership, install drivers or accept third-party licenses. Do not expose the app or the model port to a network. Local malware or an administrator can access unencrypted files and local services.

Do not report vulnerabilities by publishing secrets or personal chat data in an issue. Use GitHub's private vulnerability reporting if it is enabled by the repository owner. Submit ordinary reproducible bugs with sanitized examples.
