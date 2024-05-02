{
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";
  inputs.flake-utils.url = "github:numtide/flake-utils";
  inputs.moatt-types = {
    url = "path:../tunnel/src/moatt_types";
    inputs.nixpkgs.follows = "nixpkgs";
    inputs.flake-utils.follows = "flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils, moatt-types }:
    flake-utils.lib.eachDefaultSystem (system:
      let pkgs = nixpkgs.legacyPackages.${system};
          pyproject = builtins.fromTOML (builtins.readFile ./pyproject.toml);
          version = builtins.elemAt
            (builtins.match "^(.*\n)? *VERSION *= *\"([^\"]+)\" *(\n.*)?$"
              (builtins.readFile ./src/moat_management/__init__.py))
            1;
          python = pkgs.python3;
          deps = with python.pkgs; [
            moatt-types.packages.${system}.moatt-types

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
      in rec {
        packages = rec {
          moat-management = python.pkgs.buildPythonPackage {
            pname = pyproject.project.name;
            inherit version;
            pyproject = true;

            src = ./.;

            nativeBuildInputs = with python.pkgs; [
              setuptools
            ];

            propagatedBuildInputs = deps;
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
              Entrypoint = [ "gunicorn" "-k" "uvicorn.workers.UvicornWorker" "-b" "0.0.0.0:8000" "moat_management.main:app" ];
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
            program = "${self.packages.${system}.moat-management}/bin/moat-management";
          };

          default = moat-management;
        };

        devShells = {
          default = pkgs.mkShell {
            buildInputs = deps ++ (with python.pkgs; [
              alembic
              isort
              black
              pkgs.nodePackages.pyright
            ]);
          };

          moat-management = pkgs.mkShell {
            buildInputs = [ (python.withPackages (_: [ packages.moat-management ])) ];
          };
        };
      }
    );
}
