.. image:: https://github.com/unifyai/unifyai.github.io/blob/main/img/externally_linked/logo_dark.png?raw=true#gh-dark-mode-only
   :width: 100%
   :class: only-dark

.. image:: https://github.com/unifyai/unifyai.github.io/blob/main/img/externally_linked/logo.png?raw=true#gh-light-mode-only
   :width: 100%
   :class: only-light


.. raw:: html

    <br/>
    <a href="https://discord.gg/G4aR9Q7DTN">
        <img style="float: left; padding-right: 4px; padding-bottom: 4px;" src="https://img.shields.io/discord/799879767196958751?color=blue&label=%20&logo=discord&logoColor=white">
    </a>
    <br clear="all" />

Ivy custom pre-commit hook
==========================

This repo has a collection of pre-commit hooks that are custom to Ivy.

Installation
------------
To install the pre-commit hooks, add this to your `.pre-commit-config.yaml`:

.. code-block:: yaml

    - repos:
        - repo: https://github.com/unifyai/lint-hook
            rev: main
            hooks:
            - id: ivy-lint

Citation
--------

::

    @article{lenton2021ivy,
      title={Ivy: Templated deep learning for inter-framework portability},
      author={Lenton, Daniel and Pardo, Fabio and Falck, Fabian and James, Stephen and Clark, Ronald},
      journal={arXiv preprint arXiv:2102.02886},
      year={2021}
    }
