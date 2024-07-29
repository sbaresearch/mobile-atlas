{ pkgs
, python
}:

let pyproject = builtins.fromTOML (builtins.readFile ./pyproject.toml);
    version = builtins.elemAt
      (builtins.match "^(.*\n)? *VERSION *= *\"([^\"]+)\" *(\n.*)?$"
        (builtins.readFile ./src/wg_daemon/__init__.py))
      1;
in rec {
  dependencies = with python.pkgs; [
    fastapi
    httpx
    pydantic-settings
    systemd
    uvicorn
  ];

  packages = rec {
    wg-daemon = python.pkgs.buildPythonPackage {
      pname = pyproject.project.name;
      inherit version;
      pyproject = true;

      src = ./.;

      nativeBuildInputs = with python.pkgs; [
        setuptools
      ];

      propagatedBuildInputs = dependencies;
    };

    default = wg-daemon;
  };

  apps = rec {
    wg-daemon = {
      type = "app";
      program = "${packages.wg-daemon}/bin/wg-daemon";
    };
    default = wg-daemon;
  };
}
