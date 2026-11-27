import copy

import pytest

from peak.operational_checks import validate_release

SHA = "a" * 40


def config():
    img = lambda n: f"ghcr.io/thematthewturner/{n}:{SHA}"  # noqa: E731
    return {
        "name": "peak",
        "services": {
            "api": {"image": img("peak-backend"), "environment": {"FORWARDED_ALLOW_IPS": "172.20.0.2"}, "networks": {"default": None, "edge": None}},
            "worker": {"image": img("peak-backend"), "networks": {"default": None}},
            "web": {"image": img("peak-web")},
            "postgres": {"image": "postgres:17.9-bookworm", "networks": {"default": None}},
        },
    }


def test_valid_release():
    assert validate_release(config(), SHA) == SHA


@pytest.mark.parametrize("mutate,msg", [
    (lambda c: c["services"]["api"].update(image="x"), "GHCR"),
    (lambda c: c["services"]["web"].update(ports=["80:80"]), "host port"),
    (lambda c: c["services"]["api"]["environment"].clear(), "FORWARDED"),
    (lambda c: c["services"]["postgres"]["networks"].update(edge=None), "edge"),
    (lambda c: c.update(name="belay"), "project name"),
])
def test_rejects_bad_config(mutate, msg):
    c = copy.deepcopy(config())
    mutate(c)
    with pytest.raises(ValueError, match=msg):
        validate_release(c, SHA)


def test_rejects_short_sha():
    with pytest.raises(ValueError):
        validate_release(config(), "abc")
