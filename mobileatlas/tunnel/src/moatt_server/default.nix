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
  dependencies = with python.pkgs; [
    moatt-types

    fastapi
    httpx
    psycopg
    sqlalchemy
    uvloop
  ];

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

    moatt-server-image = pkgs.dockerTools.streamLayeredImage {
      name = "mobile-atlas-sim-tunnel";
      tag = "latest";
      contents = let
        pypkgs = python.withPackages (p: with p; [
          uvicorn
          gunicorn
          moatt-server
        ]);
        start = pkgs.writeTextFile {
          name = "simtunnel-start";
          executable = true;
          destination = "/app/start.sh";

          text = builtins.readFile ./start.sh;
        };
      in [
        pypkgs
        pkgs.dockerTools.binSh
        start
        pkgs.coreutils
      ];

      config = {
        WorkingDir = "/app";
        Entrypoint = [ "./start.sh" ];
        ExposedPorts = {
          "6666" = {};
          "8000" = {};
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
