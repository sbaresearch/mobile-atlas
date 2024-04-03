{
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";
  inputs.flake-utils.url = "github:numtide/flake-utils";
  inputs.moatt-types = {
    url = "path:../moatt_types";
    inputs.nixpkgs.follows = "nixpkgs";
    inputs.flake-utils.follows = "flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils, moatt-types }:
    flake-utils.lib.eachDefaultSystem (system:
      let pkgs = nixpkgs.legacyPackages.${system};
          python = pkgs.python3;
          pyproject = builtins.fromTOML (builtins.readFile ./pyproject.toml);
          version = builtins.elemAt
            (builtins.match "^(.*\n)? *VERSION *= *\"([^\"]+)\" *(\n.*)?$"
              (builtins.readFile ./src/moatt_server/__init__.py))
            1;
          deps = with python.pkgs; [
            moatt-types.packages.${system}.moatt-types

            fastapi
            httpx
            psycopg
            sqlalchemy
            uvloop
          ];
      in {
        packages = rec {
          moatt-server = python.pkgs.buildPythonPackage {
            pname = pyproject.project.name;
            inherit version;
            pyproject = true;

            src = ./.;

            nativeBuildInputs = with python.pkgs; [
              setuptools
            ];

            propagatedBuildInputs = deps;
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

        devShells = {
          default = pkgs.mkShell {
            buildInputs = deps ++ (with python.pkgs; [
              isort
              black
              alembic
              anyio
              pytest
              uvicorn

              pkgs.nodePackages.pyright
            ]);
          };
        };

        apps = rec {
          moat-tunnel-server = {
            type = "app";
            program = "${self.packages.${system}.moatt-server}/bin/moat-tunnel-server";
          };

          default = moat-tunnel-server;
        };
      }
    );
}
