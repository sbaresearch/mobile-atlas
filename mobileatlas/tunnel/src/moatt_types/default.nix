{ pkgs
, python
}:

let pyproject = builtins.fromTOML (builtins.readFile ./pyproject.toml);
    version = builtins.elemAt
      (builtins.match "^(.*\n)? *VERSION *= *\"([^\"]+)\" *(\n.*)?$"
        (builtins.readFile ./src/moatt_types/__init__.py))
      1;
in {
  packages = rec {
    moatt-types = python.pkgs.buildPythonPackage {
      pname = pyproject.project.name;
      inherit version;
      pyproject = true;

      src = ./.;

      nativeBuildInputs = with python.pkgs; [
        setuptools
      ];
    };
    default = moatt-types;
  };
}
