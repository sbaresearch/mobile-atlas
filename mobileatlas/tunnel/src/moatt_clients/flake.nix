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
          python = pkgs.python3;
          pyproject = builtins.fromTOML (builtins.readFile ./pyproject.toml);
          version = builtins.elemAt
            (builtins.match "^(.*\n)? *VERSION *= *\"([^\"]+)\" *(\n.*)?$"
              (builtins.readFile ./src/moatt_clients/__init__.py))
            1;
      in rec {
        packages = rec {
          moatt_clients = python.pkgs.buildPythonPackage {
            pname = pyproject.project.name;
            inherit version;
            pyproject = true;

            src = ./.;

            nativeBuildInputs = with python.pkgs; [
              setuptools
            ];

            propagatedBuildInputs = with python.pkgs; [
              moatt_types.packages.${system}.moatt_types

              requests
            ];
          };
          default = moatt_clients;
        };

        devShells = {
          default = pkgs.mkShell {
            buildInputs = with python.pkgs; [
              packages.default

              isort
              black

              pkgs.nodePackages.pyright
            ];
          };
        };
      }
    );
}
