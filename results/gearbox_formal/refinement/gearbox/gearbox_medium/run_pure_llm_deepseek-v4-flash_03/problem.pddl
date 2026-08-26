(define (problem gearbox-medium)
  (:domain image_gearbox_assembly)

  (:objects
    gearbox-housing input-shaft countershaft input-bearing-carrier - permanent-component
    dummy-support-shaft - temporary-aid
  )

  (:init
    (precedes gearbox-housing input-shaft)
    (precedes input-shaft countershaft)
    (precedes countershaft input-bearing-carrier)
    (requires-aid input-bearing-carrier dummy-support-shaft)
    (has-predecessor countershaft)
    (has-predecessor input-bearing-carrier)
    (has-predecessor input-shaft)
    (has-aid-requirement input-bearing-carrier)
    (withdraw-group-1 dummy-support-shaft input-bearing-carrier)
  )

  (:goal
    (and
      (assembled gearbox-housing)
      (assembled input-shaft)
      (assembled countershaft)
      (assembled input-bearing-carrier)
      (not (aid-present dummy-support-shaft))
    )
  )
)
