{
  inputs.nixpkgs.url = github:NixOS/nixpkgs/nixpkgs-unstable;
  inputs.flake-utils.url = github:numtide/flake-utils;
  inputs.moatt_types = {
    url = "../moatt_types";
    inputs.nixpkgs.follows = "nixpkgs";
    inputs.flake-utils.follows = "flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils, moatt_types }:
    flake-utils.lib.eachDefaultSystem (system:
      let pkgs = nixpkgs.legacyPackages.${system};
          pyproject = builtins.fromTOML (builtins.readFile ./pyproject.toml);
          version = builtins.elemAt
            (builtins.match "^(.*\n)? *VERSION *= *\"([^\"]+)\" *(\n.*)?$"
              (builtins.readFile ./src/moatt_server/__init__.py))
            1;
          python = pkgs.python3;
      in rec {
        packages = rec {
          moatt_server = python.pkgs.buildPythonApplication {
            pname = pyproject.project.name;
            inherit version;
            pyproject = true;

            src = ./.;

            nativeBuildInputs = with python.pkgs; [
              setuptools
            ];

            propagatedBuildInputs = with python.pkgs; [
              moatt_types.packages.${system}.moatt_types

              fastapi
              psycopg
              sqlalchemy
              uvloop
            ];
          };
          default = moatt_server;
        };

        devShells = {
          default = pkgs.mkShell {
            buildInputs = with python.pkgs; [
              packages.moatt_server

              isort
              black
              alembic
              anyio
              httpx
              pytest
              uvicorn

              pkgs.nodePackages.pyright
            ];
          };
        };
      }
    );
}
