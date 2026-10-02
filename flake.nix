{
  description = "Gemini Nexus DB (ping_keys) - Gemini & Gemma API key validator and stream balancer";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs { inherit system; };
        pythonEnv = pkgs.python3.withPackages (ps: with ps; [
          pyqt6
          pyqtdarktheme
          pysocks
          pytest
        ]);
      in
      {
        devShells.default = pkgs.mkShell {
          name = "ping_keys_dev_shell";
          packages = [
            pythonEnv
            pkgs.qt6.qtwayland
            pkgs.sqlite
            pkgs.ruff
          ];

          shellHook = ''
            export PYTHONUNBUFFERED=1
            export QT_QPA_PLATFORM="wayland;xcb"
            echo "🚀 [Gemini Nexus DB] Dev environment loaded (Python $(python3 --version), PyQt6 Native Wayland)"
          '';
        };

        packages.default = pkgs.writeShellApplication {
          name = "ping-keys";
          runtimeInputs = [ pythonEnv ];
          text = ''
            DIR="$(cd "$(dirname "''${BASH_SOURCE[0]}")" && pwd)"
            # Find script location relative or in cwd
            if [ -f "$PWD/ping_keys_NeuroStarNet_v13.9.py" ]; then
              exec python3 "$PWD/ping_keys_NeuroStarNet_v13.9.py" "$@"
            else
              exec python3 "${./ping_keys_NeuroStarNet_v13.9.py}" "$@"
            fi
          '';
        };

        apps.default = {
          type = "app";
          program = "${self.packages.${system}.default}/bin/ping-keys";
        };
      }
    );
}
