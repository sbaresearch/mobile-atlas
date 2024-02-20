{
  inputs.nixpkgs.url = github:NixOS/nixpkgs/nixpkgs-unstable;
  inputs.flake-utils.url = github:numtide/flake-utils;

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let pkgs = nixpkgs.legacyPackages.${system};
          python = pkgs.python3;
          pyproject = builtins.fromTOML (builtins.readFile ./pyproject.toml);
          version = builtins.elemAt
            (builtins.match "^(.*\n)? *VERSION *= *\"([^\"]+)\" *(\n.*)?$"
              (builtins.readFile ./src/moatt_types/__init__.py))
            1;
      in rec {
        packages = rec {
          moatt_types = python.pkgs.buildPythonPackage {
            pname = pyproject.project.name;
            inherit version;
            pyproject = true;

            src = ./.;

            nativeBuildInputs = with python.pkgs; [
              setuptools
            ];
          };
          default = moatt_types;
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
