{ pkgs
, python
, moatt-types
}:

let pyproject = builtins.fromTOML (builtins.readFile ./pyproject.toml);
    version = builtins.elemAt
      (builtins.match "^(.*\n)? *VERSION *= *\"([^\"]+)\" *(\n.*)?$"
        (builtins.readFile ./src/moatt_clients/__init__.py))
      1;
in rec {
  dependencies = with python.pkgs; [
    moatt-types

    requests
    pydantic
  ];

  packages = rec {
    moatt-clients = python.pkgs.buildPythonPackage {
      pname = pyproject.project.name;
      inherit version;
      pyproject = true;

      src = ./.;

      nativeBuildInputs = with python.pkgs; [
        setuptools
      ];

      propagatedBuildInputs = dependencies;
    };
    default = moatt-clients;
  };
}
