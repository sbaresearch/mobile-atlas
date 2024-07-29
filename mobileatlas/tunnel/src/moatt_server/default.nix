{ pkgs
, python
, moatt-types
}:

let pyproject = builtins.fromTOML (builtins.readFile ./pyproject.toml);
    version = builtins.elemAt
      (builtins.match "^(.*\n)? *VERSION *= *\"([^\"]+)\" *(\n.*)?$"
        (builtins.readFile ./src/moatt_server/__init__.py))
      1;
in rec {
  dependencies = (with python.pkgs; [
    fastapi
    httpx
    psycopg
    sqlalchemy
    uvloop
  ]) ++ [ moatt-types ];

  dev-dependencies = with python.pkgs; [
    uvicorn
    gunicorn
  ];

  packages = rec {
    moatt-server = python.pkgs.buildPythonPackage {
      pname = pyproject.project.name;
      inherit version;
      pyproject = true;

      src = ./.;

      nativeBuildInputs = with python.pkgs; [
        setuptools
      ];

      propagatedBuildInputs = dependencies;
    };

    moatt-restapi-image = pkgs.dockerTools.streamLayeredImage {
      name = "mobile-atlas-sim-tunnel-api";
      tag = "latest";
      contents = let
        pypkgs = python.withPackages (p: [
          p.uvicorn
          p.gunicorn
          moatt-server
        ]);
      in [
        pypkgs
        pkgs.dockerTools.binSh
        pkgs.coreutils
      ];

      config = {
        WorkingDir = "/app";
        Entrypoint = [ "gunicorn" "-k" "uvicorn.workers.UvicornWorker" "-b" "[::]:8000" "moatt_server.rest.main:app" ];
        Env = [ "PYTHONUNBUFFERED=" ];
        ExposedPorts = {
          "8000" = {};
        };
      };
    };

    moatt-server-image = pkgs.dockerTools.streamLayeredImage {
      name = "mobile-atlas-sim-tunnel";
      tag = "latest";
      contents = let
        pypkgs = python.withPackages (p: [
          moatt-server
        ]);
      in [
        pypkgs
        pkgs.dockerTools.binSh
        pkgs.coreutils
      ];

      config = {
        WorkingDir = "/app";
        Entrypoint = [ "moat-tunnel-server" "--host" "::" "0.0.0.0" "--port" "6666" ];
        Cmd = [ "--config" "/app/config/tunnel.toml" "--cert" "/app/tls/server.crt" "--cert-key" "/app/tls/server.key" ];
        Env = [ "PYTHONUNBUFFERED=" ];
        ExposedPorts = {
          "6666" = {};
        };
      };
    };

    default = moatt-server;
  };

  apps = rec {
    moat-tunnel-server = {
      type = "app";
      program = "${packages.moatt-server}/bin/moat-tunnel-server";
    };

    default = moat-tunnel-server;
  };
}
