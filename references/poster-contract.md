# Poster contract (generated)

Generated from `scripts/poster_contract.py`; edit the executable definitions, then regenerate.

The schema is a valid synthetic example, not supplied factual copy. Replace every placeholder with source text. Optional image/full-bleed fields require the legacy image route; they cannot be combined with modern vector posters.

```json
{
  "contract": {
    "type": "object",
    "properties": {
      "artifact": {
        "type": "string",
        "enum": [
          "poster"
        ]
      },
      "mode": {
        "type": "string",
        "enum": [
          "infographic",
          "editorial"
        ]
      },
      "content_plan": {
        "type": "object"
      },
      "evidence": {
        "type": "object"
      },
      "canvas": {
        "anyOf": [
          {
            "type": "string"
          },
          {
            "type": "object"
          }
        ]
      },
      "family": {
        "type": "string"
      },
      "meta": {
        "type": "object",
        "properties": {
          "palette_hex": {},
          "scale": {},
          "reverse": {},
          "family": {},
          "calibrated_from_reference": {},
          "from_content": {},
          "lang": {
            "type": "string"
          },
          "palette": {
            "type": "string"
          },
          "seed": {
            "type": "integer"
          },
          "dialect": {
            "anyOf": [
              {
                "type": "string",
                "enum": [
                  "A",
                  "B",
                  "C",
                  "D",
                  "E",
                  "F"
                ]
              },
              {
                "type": "array",
                "items": {
                  "type": "string",
                  "enum": [
                    "A",
                    "B",
                    "C",
                    "D",
                    "E",
                    "F"
                  ]
                },
                "minItems": 1,
                "maxItems": 2
              }
            ]
          },
          "elements": {
            "type": "boolean"
          },
          "fonts": {
            "type": "object",
            "additionalProperties": {
              "type": "string"
            }
          },
          "print_grammar": {
            "type": "string",
            "enum": [
              "none"
            ]
          },
          "exclude_elements": {
            "type": "array",
            "items": {
              "type": "string"
            }
          },
          "element_pool": {
            "type": "array",
            "items": {
              "type": "string"
            }
          },
          "graphic_element": {
            "type": "string"
          },
          "graphic_recipe": {
            "type": "string",
            "enum": [
              "auto",
              "off",
              "micro",
              "echo",
              "canopy",
              "terraces",
              "cut-paper",
              "hand-drawn",
              "editorial",
              "signal",
              "festival"
            ]
          },
          "topic_tags": {
            "type": "array",
            "items": {
              "type": "string"
            }
          }
        },
        "required": [],
        "additionalProperties": false
      },
      "content": {
        "type": "object",
        "properties": {
          "title": {
            "type": "string"
          },
          "subtitle": {
            "type": "string"
          },
          "date": {
            "type": "string"
          },
          "venue": {
            "type": "string"
          },
          "cta": {
            "type": "string"
          },
          "footer": {
            "type": "string"
          },
          "attribution": {
            "type": "string"
          },
          "full_bleed_reason": {
            "type": "string"
          },
          "modules": {
            "type": "array",
            "items": {
              "type": "object"
            }
          },
          "body": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "array",
                "items": {
                  "type": "string"
                }
              }
            ]
          },
          "blocks": {
            "type": "array",
            "items": {
              "anyOf": [
                {
                  "type": "string"
                },
                {
                  "type": "object",
                  "properties": {
                    "title": {
                      "type": "string"
                    },
                    "text": {
                      "type": "string"
                    }
                  },
                  "required": [],
                  "additionalProperties": false
                }
              ]
            }
          },
          "key_number": {
            "anyOf": [
              {
                "anyOf": [
                  {
                    "type": "string"
                  },
                  {
                    "type": "number"
                  }
                ]
              },
              {
                "type": "object",
                "properties": {
                  "value": {
                    "anyOf": [
                      {
                        "type": "string"
                      },
                      {
                        "type": "number"
                      }
                    ]
                  },
                  "label": {
                    "type": "string"
                  }
                },
                "required": [],
                "additionalProperties": false
              }
            ]
          },
          "quote": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "object",
                "properties": {
                  "text": {
                    "type": "string"
                  },
                  "attribution": {
                    "type": "string"
                  }
                },
                "required": [],
                "additionalProperties": false
              }
            ]
          },
          "metadata": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "array",
                "items": {
                  "type": "string"
                }
              },
              {
                "type": "object",
                "additionalProperties": {
                  "anyOf": [
                    {
                      "type": "string"
                    },
                    {
                      "type": "number"
                    }
                  ]
                }
              }
            ]
          },
          "data": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "value": {
                  "anyOf": [
                    {
                      "type": "string"
                    },
                    {
                      "type": "number"
                    }
                  ]
                },
                "label": {
                  "type": "string"
                }
              },
              "required": [],
              "additionalProperties": false
            }
          },
          "process": {
            "type": "array",
            "items": {
              "anyOf": [
                {
                  "type": "string"
                },
                {
                  "type": "object",
                  "properties": {
                    "label": {
                      "type": "string"
                    },
                    "text": {
                      "type": "string"
                    }
                  },
                  "required": [],
                  "additionalProperties": false
                }
              ]
            }
          },
          "comparison": {
            "type": "array",
            "items": {
              "anyOf": [
                {
                  "type": "string"
                },
                {
                  "type": "object",
                  "properties": {
                    "label": {
                      "type": "string"
                    },
                    "text": {
                      "type": "string"
                    }
                  },
                  "required": [],
                  "additionalProperties": false
                }
              ]
            }
          },
          "chart": {
            "type": "object",
            "properties": {
              "title": {
                "type": "string"
              },
              "unit": {
                "type": "string"
              },
              "items": {
                "type": "array",
                "items": {
                  "type": "object",
                  "properties": {
                    "label": {
                      "type": "string"
                    },
                    "value": {
                      "type": "number",
                      "minimum": 0
                    },
                    "source": {
                      "type": "string"
                    },
                    "status": {
                      "type": "string",
                      "enum": [
                        "supplied",
                        "derived",
                        "unspecified"
                      ]
                    },
                    "derivation": {
                      "type": "string"
                    }
                  },
                  "required": [
                    "label",
                    "value"
                  ],
                  "additionalProperties": false
                },
                "minItems": 2,
                "maxItems": 6
              }
            },
            "required": [
              "items"
            ],
            "additionalProperties": false
          },
          "image": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "object",
                "properties": {
                  "path": {
                    "type": "string"
                  }
                },
                "required": [
                  "path"
                ],
                "additionalProperties": false
              }
            ]
          },
          "text_bleed": {
            "type": "array",
            "items": {
              "type": "string"
            }
          }
        },
        "required": [
          "title"
        ],
        "additionalProperties": false
      },
      "layout": {
        "type": "object"
      },
      "art_direction": {
        "type": "object",
        "properties": {
          "element_density": {
            "type": "string",
            "default": "normal",
            "level": "art_direction",
            "enum": [
              "sparse",
              "normal",
              "rich"
            ]
          },
          "micro_exclude": {
            "type": "array",
            "default": [],
            "level": "art_direction"
          },
          "keep_together": {
            "type": "array",
            "default": [],
            "level": "art_direction"
          },
          "archetype": {
            "type": "string",
            "default": "auto",
            "level": "art_direction",
            "enum": [
              "auto",
              "type-hero",
              "numeral-hero",
              "diagram-hero",
              "banded",
              "staggered-modules",
              "statement"
            ]
          },
          "dialect": {
            "type": "string",
            "default": "auto",
            "level": "art_direction",
            "enum": [
              "auto",
              "swiss",
              "collage",
              "doodle"
            ]
          },
          "ink": {
            "type": "string",
            "default": "cobalt-vermilion",
            "level": "art_direction",
            "enum": [
              "cobalt-vermilion",
              "plum-ochre",
              "teal-coral"
            ]
          },
          "skeleton": {
            "type": "string",
            "default": "auto",
            "level": "art_direction",
            "enum": [
              "auto",
              "bands",
              "asymmetric-notes",
              "central-orbit"
            ]
          },
          "body_size": {
            "type": "number",
            "minimum": 16,
            "maximum": 32,
            "unit": "pt",
            "default": "20; autofit floor 16",
            "level": "art_direction"
          },
          "hero_share": {
            "type": "number",
            "minimum": 0.18,
            "maximum": 0.65,
            "unit": "safe page height fraction",
            "default": 0.24,
            "level": "art_direction"
          },
          "columns": {
            "type": "integer",
            "default": 2,
            "scope": "content columns, including blocks; never overridden by block count",
            "level": "art_direction",
            "enum": [
              1,
              2,
              3
            ]
          },
          "looseness": {
            "type": "number",
            "minimum": 0,
            "maximum": 1,
            "default": "0 swiss; .65 collage/doodle",
            "level": "art_direction"
          },
          "tiers": {
            "type": "object",
            "additionalProperties": {
              "type": "string",
              "enum": [
                "T1",
                "T2",
                "T3"
              ]
            }
          },
          "title_size": {
            "type": "number",
            "minimum": 40,
            "maximum": 80,
            "unit": "pt",
            "default": 64,
            "level": "art_direction"
          },
          "title_leading": {
            "type": "number",
            "minimum": 0.9,
            "maximum": 1.08,
            "unit": "font size fraction",
            "default": 0.98,
            "level": "art_direction"
          },
          "micro_elements": {
            "type": "boolean",
            "default": true,
            "level": "art_direction"
          },
          "autofit": {
            "type": "boolean",
            "default": true,
            "level": "art_direction"
          },
          "intentional_voids": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "rect": {
                  "type": "array",
                  "items": {
                    "type": "number"
                  },
                  "minItems": 4,
                  "maxItems": 4
                },
                "reason": {
                  "type": "string"
                }
              },
              "required": [
                "rect",
                "reason"
              ],
              "additionalProperties": false
            }
          },
          "title_lines": {
            "type": "array",
            "items": {
              "type": "string"
            }
          },
          "statement_lines": {
            "type": "array",
            "items": {
              "type": "string"
            }
          },
          "highlights": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "source": {
                  "type": "string"
                },
                "text": {
                  "type": "string"
                },
                "kind": {
                  "type": "string",
                  "enum": [
                    "highlight",
                    "circle",
                    "underline",
                    "wave",
                    "bracket"
                  ]
                }
              },
              "required": [
                "source",
                "text"
              ],
              "additionalProperties": false
            }
          },
          "roles": {
            "type": "object",
            "additionalProperties": {
              "type": "string",
              "enum": [
                "hook",
                "hero_stat",
                "parallel_set",
                "argument",
                "cta",
                "facts",
                "source",
                "meta"
              ]
            }
          },
          "micro_style": {
            "type": "string",
            "default": "label",
            "level": "art_direction",
            "enum": [
              "label",
              "stamp",
              "badge"
            ]
          },
          "revision": {
            "type": "integer",
            "minimum": 0,
            "default": 0,
            "level": "art_direction"
          },
          "review_changes": {
            "type": "array",
            "items": {
              "type": "string"
            }
          },
          "annotations": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "source": {
                  "type": "string"
                },
                "text": {
                  "type": "string"
                }
              },
              "required": [
                "source",
                "text"
              ],
              "additionalProperties": false
            }
          },
          "colophon_source": {
            "type": "string",
            "scope": "exact supplied footer",
            "level": "art_direction"
          },
          "source_document": {
            "type": "string",
            "scope": "original source text",
            "level": "art_direction"
          },
          "surface_seed": {
            "type": "integer",
            "default": "meta.seed",
            "level": "art_direction"
          },
          "halftone": {
            "type": "string",
            "default": "off",
            "level": "art_direction",
            "enum": [
              "off",
              "auto"
            ]
          }
        },
        "required": [],
        "additionalProperties": false
      },
      "brief": {
        "type": "object",
        "properties": {
          "purpose": {},
          "viewing_distance": {},
          "audience": {},
          "constraints": {},
          "sources": {}
        },
        "required": [],
        "additionalProperties": false
      }
    },
    "required": [
      "content"
    ],
    "additionalProperties": false
  },
  "content": {
    "type": "object",
    "properties": {
      "title": {
        "type": "string"
      },
      "subtitle": {
        "type": "string"
      },
      "date": {
        "type": "string"
      },
      "venue": {
        "type": "string"
      },
      "cta": {
        "type": "string"
      },
      "footer": {
        "type": "string"
      },
      "attribution": {
        "type": "string"
      },
      "full_bleed_reason": {
        "type": "string"
      },
      "modules": {
        "type": "array",
        "items": {
          "type": "object"
        }
      },
      "body": {
        "anyOf": [
          {
            "type": "string"
          },
          {
            "type": "array",
            "items": {
              "type": "string"
            }
          }
        ]
      },
      "blocks": {
        "type": "array",
        "items": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "object",
              "properties": {
                "title": {
                  "type": "string"
                },
                "text": {
                  "type": "string"
                }
              },
              "required": [],
              "additionalProperties": false
            }
          ]
        }
      },
      "key_number": {
        "anyOf": [
          {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "number"
              }
            ]
          },
          {
            "type": "object",
            "properties": {
              "value": {
                "anyOf": [
                  {
                    "type": "string"
                  },
                  {
                    "type": "number"
                  }
                ]
              },
              "label": {
                "type": "string"
              }
            },
            "required": [],
            "additionalProperties": false
          }
        ]
      },
      "quote": {
        "anyOf": [
          {
            "type": "string"
          },
          {
            "type": "object",
            "properties": {
              "text": {
                "type": "string"
              },
              "attribution": {
                "type": "string"
              }
            },
            "required": [],
            "additionalProperties": false
          }
        ]
      },
      "metadata": {
        "anyOf": [
          {
            "type": "string"
          },
          {
            "type": "array",
            "items": {
              "type": "string"
            }
          },
          {
            "type": "object",
            "additionalProperties": {
              "anyOf": [
                {
                  "type": "string"
                },
                {
                  "type": "number"
                }
              ]
            }
          }
        ]
      },
      "data": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "value": {
              "anyOf": [
                {
                  "type": "string"
                },
                {
                  "type": "number"
                }
              ]
            },
            "label": {
              "type": "string"
            }
          },
          "required": [],
          "additionalProperties": false
        }
      },
      "process": {
        "type": "array",
        "items": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "object",
              "properties": {
                "label": {
                  "type": "string"
                },
                "text": {
                  "type": "string"
                }
              },
              "required": [],
              "additionalProperties": false
            }
          ]
        }
      },
      "comparison": {
        "type": "array",
        "items": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "object",
              "properties": {
                "label": {
                  "type": "string"
                },
                "text": {
                  "type": "string"
                }
              },
              "required": [],
              "additionalProperties": false
            }
          ]
        }
      },
      "chart": {
        "type": "object",
        "properties": {
          "title": {
            "type": "string"
          },
          "unit": {
            "type": "string"
          },
          "items": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "label": {
                  "type": "string"
                },
                "value": {
                  "type": "number",
                  "minimum": 0
                },
                "source": {
                  "type": "string"
                },
                "status": {
                  "type": "string",
                  "enum": [
                    "supplied",
                    "derived",
                    "unspecified"
                  ]
                },
                "derivation": {
                  "type": "string"
                }
              },
              "required": [
                "label",
                "value"
              ],
              "additionalProperties": false
            },
            "minItems": 2,
            "maxItems": 6
          }
        },
        "required": [
          "items"
        ],
        "additionalProperties": false
      },
      "image": {
        "anyOf": [
          {
            "type": "string"
          },
          {
            "type": "object",
            "properties": {
              "path": {
                "type": "string"
              }
            },
            "required": [
              "path"
            ],
            "additionalProperties": false
          }
        ]
      },
      "text_bleed": {
        "type": "array",
        "items": {
          "type": "string"
        }
      }
    },
    "required": [
      "title"
    ],
    "additionalProperties": false
  },
  "meta": {
    "type": "object",
    "properties": {
      "palette_hex": {},
      "scale": {},
      "reverse": {},
      "family": {},
      "calibrated_from_reference": {},
      "from_content": {},
      "lang": {
        "type": "string"
      },
      "palette": {
        "type": "string"
      },
      "seed": {
        "type": "integer"
      },
      "dialect": {
        "anyOf": [
          {
            "type": "string",
            "enum": [
              "A",
              "B",
              "C",
              "D",
              "E",
              "F"
            ]
          },
          {
            "type": "array",
            "items": {
              "type": "string",
              "enum": [
                "A",
                "B",
                "C",
                "D",
                "E",
                "F"
              ]
            },
            "minItems": 1,
            "maxItems": 2
          }
        ]
      },
      "elements": {
        "type": "boolean"
      },
      "fonts": {
        "type": "object",
        "additionalProperties": {
          "type": "string"
        }
      },
      "print_grammar": {
        "type": "string",
        "enum": [
          "none"
        ]
      },
      "exclude_elements": {
        "type": "array",
        "items": {
          "type": "string"
        }
      },
      "element_pool": {
        "type": "array",
        "items": {
          "type": "string"
        }
      },
      "graphic_element": {
        "type": "string"
      },
      "graphic_recipe": {
        "type": "string",
        "enum": [
          "auto",
          "off",
          "micro",
          "echo",
          "canopy",
          "terraces",
          "cut-paper",
          "hand-drawn",
          "editorial",
          "signal",
          "festival"
        ]
      },
      "topic_tags": {
        "type": "array",
        "items": {
          "type": "string"
        }
      }
    },
    "required": [],
    "additionalProperties": false
  },
  "art_direction": {
    "element_density": {
      "type": "enum",
      "values": [
        "sparse",
        "normal",
        "rich"
      ],
      "default": "normal",
      "level": "art_direction"
    },
    "micro_exclude": {
      "type": "array",
      "default": [],
      "level": "art_direction"
    },
    "keep_together": {
      "type": "array",
      "default": [],
      "level": "art_direction"
    },
    "archetype": {
      "type": "enum",
      "values": [
        "auto",
        "type-hero",
        "numeral-hero",
        "diagram-hero",
        "banded",
        "staggered-modules",
        "statement"
      ],
      "default": "auto",
      "level": "art_direction"
    },
    "dialect": {
      "type": "enum",
      "values": [
        "auto",
        "swiss",
        "collage",
        "doodle"
      ],
      "default": "auto",
      "level": "art_direction"
    },
    "ink": {
      "type": "enum",
      "values": [
        "cobalt-vermilion",
        "plum-ochre",
        "teal-coral"
      ],
      "default": "cobalt-vermilion",
      "level": "art_direction"
    },
    "skeleton": {
      "type": "enum",
      "values": [
        "auto",
        "bands",
        "asymmetric-notes",
        "central-orbit"
      ],
      "default": "auto",
      "level": "art_direction"
    },
    "body_size": {
      "type": "number",
      "minimum": 16,
      "maximum": 32,
      "unit": "pt",
      "default": "20; autofit floor 16",
      "level": "art_direction"
    },
    "hero_share": {
      "type": "number",
      "minimum": 0.18,
      "maximum": 0.65,
      "unit": "safe page height fraction",
      "default": 0.24,
      "level": "art_direction"
    },
    "columns": {
      "type": "integer",
      "values": [
        1,
        2,
        3
      ],
      "default": 2,
      "scope": "content columns, including blocks; never overridden by block count",
      "level": "art_direction"
    },
    "looseness": {
      "type": "number",
      "minimum": 0,
      "maximum": 1,
      "default": "0 swiss; .65 collage/doodle",
      "level": "art_direction"
    },
    "tiers": {
      "type": "object",
      "values": [
        "T1",
        "T2",
        "T3"
      ],
      "default": {},
      "scope": "exact source path to user-approved hierarchy",
      "level": "art_direction"
    },
    "title_size": {
      "type": "number",
      "minimum": 40,
      "maximum": 80,
      "unit": "pt",
      "default": 64,
      "level": "art_direction"
    },
    "title_leading": {
      "type": "number",
      "minimum": 0.9,
      "maximum": 1.08,
      "unit": "font size fraction",
      "default": 0.98,
      "level": "art_direction"
    },
    "micro_elements": {
      "type": "boolean",
      "default": true,
      "level": "art_direction"
    },
    "autofit": {
      "type": "boolean",
      "default": true,
      "level": "art_direction"
    },
    "intentional_voids": {
      "type": "array",
      "default": [],
      "scope": "objects with rect [x,y,x1,y1] in pt and nonempty reason",
      "level": "art_direction"
    },
    "title_lines": {
      "type": "array",
      "scope": "exact source fragments in original order",
      "level": "art_direction"
    },
    "statement_lines": {
      "type": "array",
      "scope": "exact source quote fragments in original order",
      "level": "art_direction"
    },
    "highlights": {
      "type": "array",
      "scope": "exact source, text, optional kind; no generated keywords",
      "level": "art_direction"
    },
    "roles": {
      "type": "object",
      "scope": "exact source path to semantic role",
      "level": "art_direction"
    },
    "micro_style": {
      "type": "enum",
      "values": [
        "label",
        "stamp",
        "badge"
      ],
      "default": "label",
      "level": "art_direction"
    },
    "revision": {
      "type": "integer",
      "minimum": 0,
      "default": 0,
      "level": "art_direction"
    },
    "review_changes": {
      "type": "array",
      "default": [],
      "level": "art_direction"
    },
    "annotations": {
      "type": "array",
      "default": [],
      "scope": "source-exact phrases",
      "level": "art_direction"
    },
    "colophon_source": {
      "type": "string",
      "scope": "exact supplied footer",
      "level": "art_direction"
    },
    "source_document": {
      "type": "string",
      "scope": "original source text",
      "level": "art_direction"
    },
    "surface_seed": {
      "type": "integer",
      "default": "meta.seed",
      "level": "art_direction"
    },
    "halftone": {
      "type": "enum",
      "values": [
        "off",
        "auto"
      ],
      "default": "off",
      "level": "art_direction"
    }
  },
  "roles": [
    "hook",
    "hero_stat",
    "parallel_set",
    "argument",
    "cta",
    "facts",
    "source",
    "meta"
  ],
  "source_paths": {
    "examples": [
      "title",
      "key_number.value",
      "blocks.0.title",
      "metadata.0"
    ],
    "prefix": "No content. prefix; use exact leaf paths"
  },
  "dialect_constraints": {
    "swiss": {
      "looseness": "finite 0..1 accepted, clamped to 0 with warning"
    },
    "all": {
      "colophon_source": "If supplied, exactly content.footer; footer must then exist. If omitted, derived from existing footer."
    }
  },
  "optional_content_variants": {
    "legacy_image": {
      "image": {
        "path": "supplied-image.png"
      },
      "full_bleed_reason": "Supplied reason",
      "text_bleed": []
    }
  },
  "review": {
    "weakness_fields": [
      "location",
      "observation",
      "plan_revision"
    ],
    "example": {
      "location": "REPLACE: exact object or region",
      "observation": "REPLACE after inspecting the rendered image",
      "plan_revision": "REPLACE: concrete revision to the source spec controls"
    }
  },
  "example": {
    "artifact": "poster",
    "canvas": {
      "preset": "a3_portrait"
    },
    "family": "explainer",
    "meta": {
      "lang": "en",
      "seed": 1,
      "graphic_recipe": "micro"
    },
    "art_direction": {
      "archetype": "auto",
      "roles": {
        "title": "hook",
        "key_number.value": "hero_stat",
        "blocks.0.text": "parallel_set",
        "body": "argument",
        "cta": "cta",
        "date": "facts",
        "footer": "source",
        "metadata.0": "meta"
      },
      "tiers": {
        "title": "T1",
        "key_number.value": "T1",
        "metadata.0": "T3"
      }
    },
    "content": {
      "title": "Supplied title",
      "subtitle": "Supplied context",
      "body": [
        "Supplied paragraph.",
        "Supplied qualification."
      ],
      "key_number": {
        "value": "2",
        "label": "Supplied count"
      },
      "quote": {
        "text": "Supplied quotation.",
        "attribution": "Supplied author"
      },
      "blocks": [
        {
          "title": "Supplied heading",
          "text": "Supplied explanation."
        }
      ],
      "data": [
        {
          "value": "2",
          "label": "Supplied evidence"
        }
      ],
      "process": [
        {
          "label": "Supplied step",
          "text": "Supplied action."
        }
      ],
      "comparison": [
        {
          "label": "Supplied option",
          "text": "Supplied distinction."
        }
      ],
      "chart": {
        "title": "Supplied comparison",
        "unit": "Supplied unit",
        "items": [
          {
            "label": "Supplied A",
            "value": 1
          },
          {
            "label": "Supplied B",
            "value": 2
          }
        ]
      },
      "date": "Supplied date",
      "venue": "Supplied venue",
      "metadata": [
        "Supplied metadata"
      ],
      "attribution": "Supplied credit",
      "cta": "Supplied next step.",
      "footer": "Supplied source."
    }
  }
}
```
