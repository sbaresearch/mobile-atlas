{
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";
  inputs.flake-utils.url = "github:numtide/flake-utils";

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let pkgs = nixpkgs.legacyPackages.${system};
          python = pkgs.python3;
          moat-management-server = import ./mobileatlas/management { inherit pkgs python; };
          moat-tunnel-types = import ./mobileatlas/tunnel/src/moatt_types { inherit pkgs python; };
          moat-tunnel-server = import ./mobileatlas/tunnel/src/moatt_server { inherit pkgs python; moatt-types = moat-tunnel-types.packages.default; };
          moat-tunnel-clients = import ./mobileatlas/tunnel/src/moatt_clients { inherit pkgs python; moatt-types = moat-tunnel-types.packages.default; };
          dev-tools = with pkgs.python3.pkgs; [
            isort
            black
            pkgs.nodePackages.pyright
          ];
      in {
        packages = {
          moat-management-server = moat-management-server.packages.default;
          moat-management-server-container = moat-management-server.packages.moat-management-image;
          moat-tunnel-types = moat-tunnel-types.packages.default;
          moat-tunnel-server = moat-tunnel-server.packages.default;
          moat-tunnel-server-container = moat-tunnel-server.packages.moatt-server-image;
          moat-tunnel-clients = moat-tunnel-clients.packages.default;
        };

        devShells = let 
          attrDef = as: a: if as ? a then as.a else [];
          shellFor = p: pkgs.mkShell {
            buildInputs = builtins.concatMap (attrDef p) [ "dependencies" "dev-dependencies" ];
          };
        in {
          default = pkgs.mkShell {
            buildInputs = dev-tools ++ builtins.concatMap (p: p.dependencies ++ p.dev-dependencies) [
              moat-tunnel-server
              moat-tunnel-clients
              moat-management-server
            ];
          };

          moat-tunnel-server = shellFor moat-tunnel-server;
          moat-tunnel-clients = shellFor moat-tunnel-clients;
          moat-tunnel-types = shellFor moat-tunnel-types;
          moat-management-server = shellFor moat-management-server;
        };

        apps = {
          moat-management-server = moat-management-server.apps.default;
          moat-tunnel-server = moat-tunnel-server.apps.default;

          update-python-requirements = let
            freeze = deps: pkgs.stdenv.mkDerivation {
              pname = "freeze-py-deps";
              version = "0.0.1";

              phases = [ "buildPhase" ];

              buildInputs = deps ++ [ python.pkgs.pip ];

              buildPhase = ''
                pip --no-cache-dir freeze | grep -v '^moatt-types' >> "$out"
              '';
            };
            updateAll = pkgs.writeShellScriptBin "freeze-all-deps.sh" ''
              set -eu

              GIT_DIR="$(git rev-parse --show-toplevel)"
              cp "${freeze moat-tunnel-server.dependencies}" "$GIT_DIR/mobileatlas/tunnel/src/moatt_server/requirements.txt"
              cp "${freeze moat-tunnel-server.dev-dependencies}" "$GIT_DIR/mobileatlas/tunnel/src/moatt_server/dev-requirements.txt"

              cp "${freeze moat-tunnel-clients.dependencies}" "$GIT_DIR/mobileatlas/tunnel/src/moatt_clients/requirements.txt"

              cp "${freeze moat-management-server.dependencies}" "$GIT_DIR/mobileatlas/management/requirements.txt"
            '';
          in {
            type = "app";
            program = "${updateAll}/bin/freeze-all-deps.sh";
          };
        };
      }
    );
}
