{
  description = "Cowboy Home Assistant Integration Development Environment";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
      in
      {
        devShells.default = pkgs.mkShell {
          buildInputs = with pkgs; [
            # Python environment
            python3
            python3Packages.pip
            python3Packages.virtualenv

            # Tools used in CI/development
            yq-go    # For JSON/YAML processing
            zip     # For packaging releases
            git     # For version control

            # Development tools
            pre-commit
            black   # Python formatter
            pylint  # Python linter
          ];

          shellHook = ''
            # Create virtual environment if it doesn't exist
            if [ ! -d .venv ]; then
              echo "Creating virtual environment..."
              python -m venv .venv
            fi

            # Activate virtual environment
            source .venv/bin/activate

            # Install development dependencies if needed
            if [ ! -f .venv/.installed ]; then
              echo "Installing development dependencies..."
              pip install -e ".[dev]"
              touch .venv/.installed
            fi

            echo "Development environment ready!"
          '';
        };
      }
    );
}
