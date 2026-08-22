using .Sol: isbalanced
@assert isbalanced("") == true            "vide"
@assert isbalanced("()[]{}") == true      "plat"
@assert isbalanced("([{}])") == true      "imbrique"
@assert isbalanced("(]") == false         "croise"
@assert isbalanced("(") == false          "ouvert"
@assert isbalanced(")(") == false         "inverse"
@assert isbalanced("a(b)c[d]{e}") == true "avec texte"
@assert isbalanced("([)]") == false       "entrelace"
