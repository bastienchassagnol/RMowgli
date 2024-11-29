library(S7)

MowgliModel <- new_class("MowgliModel",
                         properties = list(
                           latentDim = class_integer,
                           highlyVariable = class_logical,
                           useModWeight = class_logical,
                           hRegularization = class_list,  # List to handle modality-specific values
                           wRegularization = class_numeric,
                           eps = class_numeric,
                           cost = class_character,
                           pcaCost = class_logical,
                           costPath = class_list,  # Optional list of paths
                           modWeight = class_list,
                           lossesW = class_list,
                           lossesH = class_list,
                           losses = class_list,
                           A = class_list,
                           H = class_list,
                           G = class_list,
                           K = class_list
                         )
)
