import os
from getpass import getpass
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization

os.chdir(os.path.dirname(__file__))

public_key = serialization.load_pem_public_key(
    Path('pubkey.pem').read_bytes())
assert isinstance(public_key, ed25519.Ed25519PublicKey)


def sign_file(path: Path, private_key):
    sig_file = path.parent / (path.name + '.sig')
    signature = private_key.sign(path.read_bytes())
    sig_file.write_bytes(signature)
    verify(path)


def verify(path: Path):
    sig_file = path.parent / (path.name + '.sig')
    public_key.verify(sig_file.read_bytes(), path.read_bytes())


if __name__ == '__main__':
    paths = ['../../Dockerfile', '../../docker-compose.yml']
    paths = [Path(p) for p in paths]
    for path in paths:
        assert path.exists()

    private_key = serialization.load_pem_private_key(
        Path('private.pem.enc').read_bytes(),
        password=getpass().encode(),
    )
    assert isinstance(private_key, ed25519.Ed25519PrivateKey)

    for path in paths:
        sign_file(path, private_key)
