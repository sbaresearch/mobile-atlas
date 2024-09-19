{
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";
  inputs.flake-utils.url = "github:numtide/flake-utils";

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let pkgs = nixpkgs.legacyPackages.${system};
          python = pkgs.python3;
          moat-management-server = import ./mobileatlas/management { inherit pkgs python; };
          wg-daemon = import ./mobileatlas/wg-daemon { inherit pkgs python; };
          moat-tunnel-types = import ./mobileatlas/tunnel/src/moatt_types { inherit pkgs python; };
          moat-tunnel-server = import ./mobileatlas/tunnel/src/moatt_server { inherit pkgs python; moatt-types = moat-tunnel-types.packages.default; };
          moat-tunnel-clients = import ./mobileatlas/tunnel/src/moatt_clients { inherit pkgs python; moatt-types = moat-tunnel-types.packages.default; };
          dev-tools = with pkgs.python3.pkgs; [
            isort
            black
            pkgs.pyright
          ];
      in rec {
        packages = {
          moat-management-server = moat-management-server.packages.default;
          moat-management-server-container = moat-management-server.packages.moat-management-image;
          wg-daemon = wg-daemon.packages.wg-daemon;
          moat-tunnel-types = moat-tunnel-types.packages.default;
          moat-tunnel-server = moat-tunnel-server.packages.default;
          moat-tunnel-server-container = moat-tunnel-server.packages.moatt-server-image;
          moat-tunnel-restapi-container = moat-tunnel-server.packages.moatt-restapi-image;
          moat-tunnel-clients = moat-tunnel-clients.packages.default;
        };

        devShells = let 
          attrDef = as: a: if pkgs.lib.hasAttr a as then as."${a}" else [];
          shellFor = p: pkgs.mkShell {
            buildInputs = builtins.concatMap (attrDef p) [ "dependencies" "dev-dependencies" ];
          };
        in {
          default = pkgs.mkShell {
            buildInputs = dev-tools ++ builtins.concatMap (p: attrDef p "dependencies" ++ attrDef p "dev-dependencies") [
              moat-tunnel-server
              moat-tunnel-clients
              moat-management-server
              wg-daemon
            ];
          };

          moat-tunnel-server = shellFor moat-tunnel-server;
          moat-tunnel-clients = shellFor moat-tunnel-clients;
          moat-tunnel-types = shellFor moat-tunnel-types;
          moat-management-server = shellFor moat-management-server;
          wg-daemon = shellFor wg-daemon;
        };

        apps = {
          moat-management-server = moat-management-server.apps.default;
          wg-daemon = wg-daemon.apps.default;
          moat-tunnel-server = moat-tunnel-server.apps.default;
          moat-management-server-container = {
            type = "app";
            program = "${packages.moat-management-server-container}";
          };
          moat-tunnel-server-container = {
            type = "app";
            program = "${packages.moat-tunnel-server-container}";
          };
          moat-tunnel-restapi-container = {
            type = "app";
            program = "${packages.moat-tunnel-restapi-container}";
          };

          update-python-requirements = let
            freeze = lib: deps: pkgs.stdenv.mkDerivation {
              pname = "freeze-py-deps";
              version = "0.0.1";

              phases = [ "buildPhase" ];

              buildInputs = deps ++ [ python.pkgs.pip ];

              buildPhase = let 
                depsPat = builtins.concatStringsSep "|" (builtins.map (d: d.pname) deps);
              in if lib then ''
                pip --no-cache-dir freeze | sed -nE '/^moatt-types/d;/^${depsPat}==/s/^(.*)==(([0-9]+!)?[0-9]+(\.[0-9]+)?).*$/\1~=\2/p' >> "$out"
              '' else ''
                pip --no-cache-dir freeze | grep -v '^moatt-types' >> "$out"
              '';
            };
            updateAll = pkgs.writeShellScriptBin "freeze-all-deps.sh" ''
              set -eu

              if ! diff -q ${./flake.nix} ./flake.nix &>/dev/null; then
                echo "ERROR: Please run this script from the project's root directory."
                exit 1
              fi

              cp "${freeze false moat-tunnel-server.dependencies}" "./mobileatlas/tunnel/src/moatt_server/requirements.txt"
              cp "${freeze false moat-tunnel-server.dev-dependencies}" "./mobileatlas/tunnel/src/moatt_server/dev-requirements.txt"

              cp "${freeze true moat-tunnel-clients.dependencies}" "./mobileatlas/tunnel/src/moatt_clients/requirements.txt"

              cp "${freeze false moat-management-server.dependencies}" "./mobileatlas/management/requirements.txt"
              cp "${freeze false wg-daemon.dependencies}" "./mobileatlas/wg-daemon/requirements.txt"
            '';
          in {
            type = "app";
            program = "${updateAll}/bin/freeze-all-deps.sh";
          };
        };
      }
    );
}
