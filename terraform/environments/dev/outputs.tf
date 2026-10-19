/**
 * Aggregated Fleet Infrastructure Outputs for Dev Environment
 * GCP Health Data Platform POC
 */

output "hub_infrastructure" {
  description = "Central Management Hub provisioned endpoints and datasets"
  value = {
    project_id            = module.hub.hub_project_id
    registry_dataset_id   = module.hub.hub_registry_dataset_id
    telemetry_dataset_id  = module.hub.hub_telemetry_dataset_id
    shared_clinical_id    = module.hub.hub_shared_clinical_dataset_id
    shared_reference_id   = module.hub.hub_shared_reference_dataset_id
    billing_view_id       = module.hub.view_billing_export_id
    backend_sa_email      = module.hub.hub_backend_service_account_email
  }
}

output "spoke_research_rooms" {
  description = "Provisioned spoke research rooms across the enterprise fleet"
  value = {
    oncology = {
      room_id          = module.room_oncology_01.room_id
      project_id       = module.room_oncology_01.spoke_project_id
      inbound_bucket   = module.room_oncology_01.inbound_bucket_url
      export_bucket    = module.room_oncology_01.export_bucket_url
      local_dataset    = module.room_oncology_01.local_dataset_id
      group_email      = module.room_oncology_01.identity_group_email
      workbench_id     = module.room_oncology_01.workbench_instance_id
    }
    genomics = {
      room_id          = module.room_genomics_02.room_id
      project_id       = module.room_genomics_02.spoke_project_id
      inbound_bucket   = module.room_genomics_02.inbound_bucket_url
      export_bucket    = module.room_genomics_02.export_bucket_url
      local_dataset    = module.room_genomics_02.local_dataset_id
      group_email      = module.room_genomics_02.identity_group_email
      workbench_id     = module.room_genomics_02.workbench_instance_id
    }
    cardio = {
      room_id          = module.room_cardio_03.room_id
      project_id       = module.room_cardio_03.spoke_project_id
      inbound_bucket   = module.room_cardio_03.inbound_bucket_url
      export_bucket    = module.room_cardio_03.export_bucket_url
      local_dataset    = module.room_cardio_03.local_dataset_id
      group_email      = module.room_cardio_03.identity_group_email
      workbench_id     = module.room_cardio_03.workbench_instance_id
    }
    neurology = {
      room_id          = module.room_neurology_04.room_id
      project_id       = module.room_neurology_04.spoke_project_id
      inbound_bucket   = module.room_neurology_04.inbound_bucket_url
      export_bucket    = module.room_neurology_04.export_bucket_url
      local_dataset    = module.room_neurology_04.local_dataset_id
      group_email      = module.room_neurology_04.identity_group_email
      workbench_id     = module.room_neurology_04.workbench_instance_id
    }
  }
}
