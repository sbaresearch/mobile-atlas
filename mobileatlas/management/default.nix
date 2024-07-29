{ pkgs
, python
}:

let pyproject = builtins.fromTOML (builtins.readFile ./pyproject.toml);
    version = builtins.elemAt
      (builtins.match "^(.*\n)? *VERSION *= *\"([^\"]+)\" *(\n.*)?$"
        (builtins.readFile ./src/moat_management/__init__.py))
      1;
in rec {
  dependencies = with python.pkgs; [
    fastapi
    httpx
    jinja2
    psycopg
    pycountry
    python-multipart
    redis
    sqlalchemy
    uvicorn
    uvloop
  ];

  packages = rec {
    moat-management = python.pkgs.buildPythonPackage {
      pname = pyproject.project.name;
      inherit version;
      pyproject = true;

      src = ./.;

      nativeBuildInputs = with python.pkgs; [
        setuptools
      ];

      propagatedBuildInputs = dependencies;
    };

    moat-management-image = pkgs.dockerTools.streamLayeredImage {
      name = "mobile-atlas-management";
      tag = "latest";
      contents = let
        pypkgs = python.withPackages (p: with p; [
          uvicorn
          gunicorn
          moat-management
        ]);
      in [
        pypkgs
        pkgs.dockerTools.binSh
        pkgs.coreutils
      ];

      config = {
        WorkingDir = "/app";
        Entrypoint = [ "gunicorn" "-k" "uvicorn.workers.UvicornWorker" "-b" "[::]:8000" "moat_management.main:app" ];
        Env = [ "PYTHONUNBUFFERED=1" ];
        ExposedPorts = {
          "8000" = {};
        };
      };
    };

    default = moat-management;
  };

  apps = rec {
    moat-management = {
      type = "app";
      program = "${packages.moat-management}/bin/moat-management";
    };
    default = moat-management;
  };
}
