(define (problem gearbox-hard)
  (:domain image_gearbox_assembly)

  (:objects
    gearbox-housing input-shaft countershaft input-bearing-carrier countershaft-bearing-carrier drive-gear-assembly countershaft-gear-assembly output-gear-assembly - permanent-component
    dummy-support-shaft - temporary-aid
  )

  (:init
    (precedes gearbox-housing input-shaft)
    (precedes gearbox-housing countershaft)
    (precedes input-shaft input-bearing-carrier)
    (precedes countershaft countershaft-bearing-carrier)
    (precedes input-bearing-carrier drive-gear-assembly)
    (precedes countershaft-bearing-carrier countershaft-gear-assembly)
    (precedes drive-gear-assembly output-gear-assembly)
    (requires-aid countershaft-gear-assembly dummy-support-shaft)
    (requires-aid output-gear-assembly dummy-support-shaft)
    (has-predecessor countershaft)
    (has-predecessor countershaft-bearing-carrier)
    (has-predecessor countershaft-gear-assembly)
    (has-predecessor drive-gear-assembly)
    (has-predecessor input-bearing-carrier)
    (has-predecessor input-shaft)
    (has-predecessor output-gear-assembly)
    (has-aid-requirement countershaft-gear-assembly)
    (has-aid-requirement output-gear-assembly)
    (withdraw-group-2 dummy-support-shaft countershaft-gear-assembly output-gear-assembly)
  )

  (:goal
    (and
      (assembled gearbox-housing)
      (assembled input-shaft)
      (assembled countershaft)
      (assembled input-bearing-carrier)
      (assembled countershaft-bearing-carrier)
      (assembled drive-gear-assembly)
      (assembled countershaft-gear-assembly)
      (assembled output-gear-assembly)
      (not (aid-present dummy-support-shaft))
    )
  )
)
