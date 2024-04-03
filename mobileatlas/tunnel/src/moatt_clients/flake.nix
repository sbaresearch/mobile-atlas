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
              (builtins.readFile ./src/moatt_clients/__init__.py))
            1;
          deps = with python.pkgs; [
            moatt-types.packages.${system}.moatt-types

            requests
            pydantic
          ];
      in {
        packages = rec {
          moatt-clients = python.pkgs.buildPythonPackage {
            pname = pyproject.project.name;
            inherit version;
            pyproject = true;

            src = ./.;

            nativeBuildInputs = with python.pkgs; [
              setuptools
            ];

            propagatedBuildInputs = deps;
          };
          default = moatt-clients;
        };

        devShells = {
          default = pkgs.mkShell {
            buildInputs = deps ++ (with python.pkgs; [
              isort
              black
              pkgs.nodePackages.pyright
            ]);
          };
        };
      }
    );
}
